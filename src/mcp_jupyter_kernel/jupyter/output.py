"""Iopub-message accumulator. Shared between server-mode and standalone-mode.

Tracks the canonical "cell is done" condition: both `status:idle` on iopub
AND `execute_reply` on shell have arrived for the same parent_header.msg_id.
Either alone is unsafe — see docs/recon/jupyter-api.md §2.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionState:
    """Accumulates iopub + shell messages for one execute_request."""

    parent_msg_id: str
    outputs: list[dict[str, Any]] = field(default_factory=list)
    execution_count: int | None = None
    error: dict[str, Any] | None = None  # {ename, evalue, traceback}
    last_plot: dict[str, Any] | None = None  # {image_png_base64, source}
    _iopub_idle: bool = False
    _shell_reply: dict[str, Any] | None = None
    _started_at: float = field(default_factory=time.monotonic)

    def wall_time_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)

    def on_iopub(self, msg: dict[str, Any]) -> None:
        if msg.get("parent_header", {}).get("msg_id") != self.parent_msg_id:
            return
        t = msg["msg_type"]
        c = msg["content"]

        if t == "status":
            if c.get("execution_state") == "idle":
                self._iopub_idle = True
        elif t == "execute_input":
            if c.get("execution_count") is not None:
                self.execution_count = c["execution_count"]
        elif t == "stream":
            self.outputs.append(
                {"output_type": "stream", "name": c["name"], "text": c["text"]}
            )
        elif t == "execute_result":
            self.outputs.append(
                {
                    "output_type": "execute_result",
                    "execution_count": c.get("execution_count"),
                    "data": c.get("data", {}),
                    "metadata": c.get("metadata", {}),
                }
            )
            self._capture_plot_from(c.get("data", {}))
        elif t == "display_data":
            self.outputs.append(
                {
                    "output_type": "display_data",
                    "data": c.get("data", {}),
                    "metadata": c.get("metadata", {}),
                }
            )
            self._capture_plot_from(c.get("data", {}))
        elif t == "error":
            err = {
                "ename": c.get("ename", ""),
                "evalue": c.get("evalue", ""),
                "traceback": c.get("traceback", []),
            }
            self.error = err
            self.outputs.append({"output_type": "error", **err})

    def on_shell_reply(self, msg: dict[str, Any]) -> None:
        if msg.get("parent_header", {}).get("msg_id") != self.parent_msg_id:
            return
        self._shell_reply = msg["content"]
        if msg["content"].get("execution_count") is not None:
            self.execution_count = msg["content"]["execution_count"]

    def is_done(self) -> bool:
        return self._iopub_idle and self._shell_reply is not None

    def final_status(self) -> str:
        """'ok' | 'error' | 'timeout' (caller sets timeout)."""
        if self._shell_reply is None:
            return "timeout"
        reply_status = self._shell_reply.get("status", "")
        return "error" if reply_status == "error" else "ok"

    def _capture_plot_from(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        if "image/png" in data:
            png = data["image/png"]
            # iopub PNG payloads are already base64 strings.
            if isinstance(png, bytes):
                png = base64.b64encode(png).decode("ascii")
            source = "matplotlib"
            if "application/vnd.plotly.v1+json" in data:
                source = "plotly"
            elif "application/vnd.vegalite.v5+json" in data or "application/vnd.vega.v5+json" in data:
                source = "altair"
            self.last_plot = {"image_png_base64": png, "source": source}
