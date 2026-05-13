"""Server-mode KernelSession: REST + WebSocket against a running jupyter_server.

Uses httpx for REST and websockets for the kernel channel directly, not the
sync jupyter-kernel-client. Going direct is a couple hundred lines and lets
respx mock the wire layer cleanly.

The WS frames are JSON. The binary `v1.kernel.websocket.jupyter.org`
subprotocol would cut plot-heavy payloads ~33% but isn't required for
correctness; TODO.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import uuid
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import websockets

from ..auth import auth_headers, resolve_token
from ..config import JupyterConfig
from ..helpers.bootstrap import KERNEL_HELPER_SRC
from . import nb
from .output import ExecutionState
from .session import ExecuteResult, KernelSession, NotebookHandle


class ServerSession(KernelSession):
    """Talks to a running jupyter_server over REST + WS.

    Notebook IDs are session IDs from /api/sessions; they tie a notebook
    path to a kernel.
    """

    def __init__(self, cfg: JupyterConfig, token_override: str | None = None) -> None:
        self.cfg = cfg
        self.token = resolve_token(cfg, token_override)
        self._http: httpx.AsyncClient | None = None
        # Cache of session_id → (path, kernel_id, last_modified).
        self._sessions_cache: dict[str, dict[str, Any]] = {}
        # Per-kernel WS connection (id → websocket).
        self._ws: dict[str, Any] = {}
        # Per-kernel plot/error capture state (shared across executes).
        self._last_plot: dict[str, Any] | None = None
        self._last_error: dict[str, Any] | None = None
        # Serialize execution within a single kernel.
        self._locks: dict[str, asyncio.Lock] = {}
        # Kernel IDs that have had the __mjk helper namespace injected. Bootstrap
        # is per-kernel because one ServerSession can span multiple kernels.
        self._bootstrapped: set[str] = set()

    # ---------- REST ----------

    @property
    def base_url(self) -> str:
        return self.cfg.url.rstrip("/") + self.cfg.base_url_prefix

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers=auth_headers(self.token),
                verify=self.cfg.verify_tls,
                timeout=30.0,
            )
        return self._http

    async def _get(self, path: str, **params: Any) -> Any:
        http = await self._ensure_http()
        r = await http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    async def _put(self, path: str, payload: dict[str, Any]) -> Any:
        http = await self._ensure_http()
        r = await http.put(path, json=payload)
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        http = await self._ensure_http()
        r = await http.post(path, json=payload or {})
        r.raise_for_status()
        if r.text:
            return r.json()
        return None

    # ---------- KernelSession interface ----------

    async def list_notebooks(self) -> list[NotebookHandle]:
        sessions = await self._get("/api/sessions")
        out = []
        for s in sessions:
            if s.get("type") != "notebook":
                continue
            kernel = s.get("kernel") or {}
            kernel_id = kernel.get("id", "")
            path = s.get("path") or s.get("name") or ""
            sid = s["id"]
            self._sessions_cache[sid] = {
                "path": path,
                "kernel_id": kernel_id,
                "last_modified": None,
            }
            out.append(
                NotebookHandle(
                    notebook_id=sid,
                    path=path,
                    kernel_id=kernel_id,
                    kernel_status=kernel.get("execution_state", "idle"),
                    last_activity=kernel.get("last_activity"),
                )
            )
        return out

    async def read_cells(self, notebook_id: str, n: int) -> list[dict[str, Any]]:
        path = self._cached_path(notebook_id)
        contents = await self._get(
            f"/api/contents/{_url_path(path)}", content=1
        )
        self._sessions_cache[notebook_id]["last_modified"] = contents.get("last_modified")
        notebook = contents.get("content", {})
        cells = notebook.get("cells", []) or []
        total = len(cells)
        start = max(0, total - n)
        out: list[dict[str, Any]] = []
        for i in range(start, total):
            c = cells[i]
            entry: dict[str, Any] = {
                "index": i,
                "cell_type": c.get("cell_type", "code"),
                "source": _join_source(c.get("source", "")),
            }
            if c.get("cell_type") == "code":
                entry["outputs"] = c.get("outputs", [])
                entry["execution_count"] = c.get("execution_count")
            out.append(entry)
        return out

    async def insert_cell(
        self,
        notebook_id: str,
        after_index: int,
        code: str,
        cell_type: str = "code",
    ) -> int:
        path = self._cached_path(notebook_id)
        # RTC-safe: read, check last_modified, modify, write only if unchanged.
        contents = await self._get(
            f"/api/contents/{_url_path(path)}", content=1
        )
        original_modified = contents.get("last_modified")
        notebook = contents["content"]
        cells = notebook.get("cells", []) or []
        new_cell = (
            nb.new_code_cell(code) if cell_type == "code" else nb.new_markdown_cell(code)
        )
        if "id" not in new_cell:
            new_cell["id"] = uuid.uuid4().hex[:8]
        insert_at = max(0, min(len(cells), after_index + 1))
        cells.insert(insert_at, dict(new_cell))
        notebook["cells"] = cells

        # Conflict check: re-fetch (cheap; content=0 omits the body) and compare.
        recheck = await self._get(
            f"/api/contents/{_url_path(path)}", content=0
        )
        if recheck.get("last_modified") != original_modified:
            raise ConcurrentModificationError(
                f"notebook {path} changed since read (was {original_modified}, "
                f"now {recheck.get('last_modified')}). Re-read and retry."
            )

        await self._put(
            f"/api/contents/{_url_path(path)}",
            {"type": "notebook", "format": "json", "content": notebook},
        )
        return insert_at

    async def execute_cell(
        self, notebook_id: str, cell_index: int, timeout_s: int
    ) -> ExecuteResult:
        path = self._cached_path(notebook_id)
        # Read current cell source from disk view.
        contents = await self._get(
            f"/api/contents/{_url_path(path)}", content=1
        )
        notebook = contents["content"]
        cells = notebook.get("cells", []) or []
        if not (0 <= cell_index < len(cells)):
            raise IndexError(f"cell_index {cell_index} out of range [0,{len(cells)})")
        cell = cells[cell_index]
        if cell.get("cell_type") != "code":
            return ExecuteResult(outputs=[], status="ok", execution_count=None, wall_time_ms=0)
        code = _join_source(cell.get("source", ""))
        result = await self._execute_via_ws(notebook_id, code, timeout_s, silent=False, store_history=True)

        # Persist outputs + execution_count back to disk so Lab sees them.
        cell["outputs"] = result.outputs
        cell["execution_count"] = result.execution_count
        await self._put(
            f"/api/contents/{_url_path(path)}",
            {"type": "notebook", "format": "json", "content": notebook},
        )
        return result

    async def execute_code(
        self,
        notebook_id: str,
        code: str,
        timeout_s: int,
        silent: bool = False,
    ) -> ExecuteResult:
        return await self._execute_via_ws(
            notebook_id, code, timeout_s, silent=silent, store_history=False
        )

    async def cancel(self, notebook_id: str) -> dict[str, Any]:
        kernel_id = self._cached_kernel(notebook_id)
        was_busy = self._locks.get(kernel_id, asyncio.Lock()).locked()
        await self._post(f"/api/kernels/{kernel_id}/interrupt")
        return {"interrupted": True, "was_busy": was_busy}

    async def close(self) -> None:
        for ws in self._ws.values():
            with contextlib.suppress(Exception):
                await ws.close()
        self._ws.clear()
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def get_last_plot(self) -> dict[str, Any] | None:
        return dict(self._last_plot) if self._last_plot else None

    def get_last_error(self) -> dict[str, Any] | None:
        return dict(self._last_error) if self._last_error else None

    # ---------- WebSocket execution ----------

    async def _bootstrap_helpers(self, kernel_id: str) -> None:
        """Inject the __mjk helper namespace into the kernel once.

        kernel.list_variables and inspect tools all build kernel-side
        expressions that reference `__mjk` and `__mjk_json`. Without this
        bootstrap they fail with NameError on the first call.
        """
        if kernel_id in self._bootstrapped:
            return
        # Mark first so the recursive _execute_via_ws_raw call doesn't re-enter
        # via execute_code's bootstrap check (it doesn't today, but this keeps
        # the invariant defensive).
        self._bootstrapped.add(kernel_id)
        await self._execute_via_ws_raw(
            kernel_id,
            KERNEL_HELPER_SRC,
            timeout_s=10,
            silent=True,
            store_history=False,
        )

    async def _execute_via_ws(
        self,
        notebook_id: str,
        code: str,
        timeout_s: int,
        silent: bool,
        store_history: bool,
    ) -> ExecuteResult:
        kernel_id = self._cached_kernel(notebook_id)
        await self._bootstrap_helpers(kernel_id)
        return await self._execute_via_ws_raw(
            kernel_id, code, timeout_s, silent, store_history
        )

    async def _execute_via_ws_raw(
        self,
        kernel_id: str,
        code: str,
        timeout_s: int,
        silent: bool,
        store_history: bool,
    ) -> ExecuteResult:
        lock = self._locks.setdefault(kernel_id, asyncio.Lock())
        async with lock:
            ws = await self._ensure_ws(kernel_id)
            msg_id = uuid.uuid4().hex
            session_id = uuid.uuid4().hex

            request = {
                "channel": "shell",
                "header": {
                    "msg_id": msg_id,
                    "session": session_id,
                    "username": "mcp-jupyter-kernel",
                    "date": datetime.datetime.now(datetime.UTC).isoformat(),
                    "msg_type": "execute_request",
                    "version": "5.3",
                },
                "parent_header": {},
                "metadata": {},
                "content": {
                    "code": code,
                    "silent": silent,
                    "store_history": store_history,
                    "user_expressions": {},
                    "allow_stdin": False,
                    "stop_on_error": True,
                },
                "buffers": [],
            }

            await ws.send(json.dumps(request))
            state = ExecutionState(parent_msg_id=msg_id)

            async def pump() -> None:
                while not state.is_done():
                    raw = await ws.recv()
                    msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    channel = msg.get("channel", "")
                    if channel == "iopub":
                        state.on_iopub(msg)
                    elif channel == "shell":
                        state.on_shell_reply(msg)

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(pump(), timeout=timeout_s)

            if not silent:
                if state.last_plot:
                    self._last_plot = dict(state.last_plot)
                if state.error:
                    self._last_error = dict(state.error)

            return ExecuteResult(
                outputs=state.outputs,
                status=state.final_status() if state.is_done() else "timeout",
                execution_count=state.execution_count,
                wall_time_ms=state.wall_time_ms(),
            )

    async def _ensure_ws(self, kernel_id: str) -> Any:
        if kernel_id in self._ws:
            return self._ws[kernel_id]
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = (
            f"{scheme}://{parsed.netloc}{parsed.path}"
            f"/api/kernels/{kernel_id}/channels?token={self.token}"
        )
        # Token in query string for compatibility. Header-based auth on the
        # WS handshake is supported by jupyter_server but flaky across clients.
        ws = await websockets.connect(ws_url, max_size=None)
        self._ws[kernel_id] = ws
        return ws

    # ---------- helpers ----------

    def _cached_path(self, notebook_id: str) -> str:
        if notebook_id not in self._sessions_cache:
            raise KeyError(
                f"unknown notebook_id {notebook_id!r}; call notebooks.list_open first"
            )
        return self._sessions_cache[notebook_id]["path"]

    def _cached_kernel(self, notebook_id: str) -> str:
        if notebook_id not in self._sessions_cache:
            raise KeyError(
                f"unknown notebook_id {notebook_id!r}; call notebooks.list_open first"
            )
        return self._sessions_cache[notebook_id]["kernel_id"]


class ConcurrentModificationError(RuntimeError):
    """The notebook changed on disk between our read and write."""


def _url_path(p: str) -> str:
    # Jupyter contents paths are URL path segments; encode each.
    return "/".join(quote(seg, safe="") for seg in p.split("/") if seg)


def _join_source(src: Any) -> str:
    if isinstance(src, list):
        return "".join(src)
    return str(src)
