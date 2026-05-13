"""Polymorphic `inspect` tool.

The `mode` argument carries the privacy posture:
  auto    -> type-aware summaries (shape, dtypes, head)
  summary -> describe() / value_counts() / numeric stats
  value   -> raw repr, capped at 50 KB
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from ..helpers.bootstrap import helper_call
from .kernel_ import _parse_helper_output

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession

_VALUE_MODE_WARNING = (
    "WARNING: mode='value' returns raw kernel values which may contain "
    "sensitive data (PII, secrets, customer values). ONLY use when the user "
    "explicitly asks to see actual values."
)


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="inspect",
        description=(
            "Inspect a kernel value. `target` is a variable name OR a Python "
            "expression (e.g. 'df.dtypes', 'len(rows)'). Modes:\n"
            "  - 'auto' (default, SAFE): type-aware summary. DataFrame → "
            "shape+dtypes+head(5). ndarray → shape+dtype+head. Other → repr "
            "capped at 1KB.\n"
            "  - 'summary' (SAFE): DataFrame.describe() + top-K value_counts "
            "for low-cardinality categoricals. ndarray → stats.\n"
            f"  - 'value' (UNSAFE): raw repr capped at 50KB. {_VALUE_MODE_WARNING}\n"
            "Default to 'auto'. Escalate to 'summary' for richer statistics. "
            "Escalate to 'value' only on explicit user ask."
        ),
    )
    async def inspect(
        notebook_id: str,
        target: str,
        mode: Literal["auto", "summary", "value"] = "auto",
    ) -> dict[str, Any]:
        if mode == "auto":
            code = helper_call("inspect_auto", target)
        elif mode == "summary":
            code = helper_call("inspect_summary", target)
        elif mode == "value":
            code = helper_call("inspect_value", target)
        else:
            return {"error": f"unknown mode: {mode}"}

        # silent=False so the helper's print(json) reaches us via stream output.
        result = await session.execute_code(notebook_id, code, timeout_s=30, silent=False)
        payload = _parse_helper_output(result.outputs)
        if payload is None:
            return {"error": "helper_output_unavailable", "raw_outputs": result.outputs}
        return {"mode_used": mode, "summary": payload}
