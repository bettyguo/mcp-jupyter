"""Standalone-mode KernelSession.

Spawns a kernel via jupyter_client. Single notebook per session, no
Jupyter server in the loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import sys
import uuid
from pathlib import Path
from typing import Any

from ..config import StandaloneConfig
from ..helpers.bootstrap import KERNEL_HELPER_SRC
from . import nb
from .output import ExecutionState
from .session import ExecuteResult, KernelSession, NotebookHandle

_NOTEBOOK_ID = "local"


class StandaloneSession(KernelSession):
    def __init__(self, cfg: StandaloneConfig) -> None:
        self.cfg = cfg
        self._km: Any | None = None
        self._kc: Any | None = None
        self._notebook: Any | None = None
        self._notebook_path: Path | None = None
        self._notebook_dirty = False
        self._bootstrapped = False
        self._last_plot: dict[str, Any] | None = None
        self._last_error: dict[str, Any] | None = None
        self._last_error_cell: int | None = None
        self._current_cell_index: int | None = None
        self._kernel_id: str = "standalone-pending"
        self._lock = asyncio.Lock()  # serialize executes

    async def start(self) -> None:
        # Windows + jupyter_client async pre-flight: prefer Selector loop.
        if sys.platform == "win32":
            try:
                policy = asyncio.get_event_loop_policy()
                if not isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            except AttributeError:
                pass

        from jupyter_client.manager import AsyncKernelManager

        self._km = AsyncKernelManager(kernel_name=self.cfg.kernel_name)
        if self.cfg.cwd:
            await self._km.start_kernel(cwd=self.cfg.cwd)
        else:
            await self._km.start_kernel()
        self._kernel_id = self._km.kernel_id
        self._kc = self._km.client()
        self._kc.start_channels()
        await self._kc.wait_for_ready(timeout=30)

        if self.cfg.notebook_path:
            p = Path(self.cfg.notebook_path)
            self._notebook_path = p
            if p.exists():
                self._notebook = nb.read_notebook(p)
            else:
                self._notebook = nb.new_notebook()
                self._notebook_dirty = True
        else:
            self._notebook = nb.new_notebook()

    async def _bootstrap_helpers(self) -> None:
        if self._bootstrapped:
            return
        # Mark first so re-entry from execute_code -> _bootstrap doesn't recurse.
        self._bootstrapped = True
        await self._execute_internal(
            KERNEL_HELPER_SRC, timeout_s=10, silent=True, store_history=False
        )

    async def _execute_internal(
        self, code: str, timeout_s: int, silent: bool, store_history: bool
    ) -> ExecuteResult:
        assert self._kc is not None
        async with self._lock:
            msg_id = self._kc.execute(
                code,
                silent=silent,
                store_history=store_history,
                allow_stdin=False,
                stop_on_error=True,
            )
            state = ExecutionState(parent_msg_id=msg_id)

            async def consume_iopub() -> None:
                while not state.is_done():
                    try:
                        msg = await self._kc.get_iopub_msg(timeout=timeout_s)
                    except Exception:
                        return
                    state.on_iopub(msg)

            async def consume_shell() -> None:
                while state._shell_reply is None:
                    try:
                        msg = await self._kc.get_shell_msg(timeout=timeout_s)
                    except Exception:
                        return
                    state.on_shell_reply(msg)

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(consume_iopub(), consume_shell()),
                    timeout=timeout_s,
                )

            # Persist plot/error capture (not silent-mode helper calls).
            if not silent:
                if state.last_plot:
                    self._last_plot = dict(state.last_plot)
                    if self._current_cell_index is not None:
                        self._last_plot["cell_index"] = self._current_cell_index
                if state.error:
                    self._last_error = dict(state.error)
                    self._last_error_cell = self._current_cell_index

            return ExecuteResult(
                outputs=state.outputs,
                status=state.final_status() if state.is_done() else "timeout",
                execution_count=state.execution_count,
                wall_time_ms=state.wall_time_ms(),
            )

    # ---------- KernelSession interface ----------

    async def list_notebooks(self) -> list[NotebookHandle]:
        return [
            NotebookHandle(
                notebook_id=_NOTEBOOK_ID,
                path=str(self._notebook_path) if self._notebook_path else None,
                kernel_id=self._kernel_id,
                kernel_status="idle",
                last_activity=datetime.datetime.now(datetime.UTC).isoformat(),
            )
        ]

    async def read_cells(self, notebook_id: str, n: int) -> list[dict[str, Any]]:
        self._require(notebook_id)
        cells = self._notebook.cells if self._notebook else []
        total = len(cells)
        start = max(0, total - n)
        out = []
        for i in range(start, total):
            c = cells[i]
            entry: dict[str, Any] = {
                "index": i,
                "cell_type": c.get("cell_type", "code"),
                "source": c.get("source", ""),
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
        self._require(notebook_id)
        cells = self._notebook.cells
        new_cell = (
            nb.new_code_cell(code) if cell_type == "code" else nb.new_markdown_cell(code)
        )
        # Ensure cell has an id field for nbformat v4.5+.
        if "id" not in new_cell:
            new_cell["id"] = uuid.uuid4().hex[:8]
        insert_at = max(0, min(len(cells), after_index + 1))
        cells.insert(insert_at, new_cell)
        self._notebook_dirty = True
        self._maybe_persist()
        return insert_at

    async def execute_cell(
        self, notebook_id: str, cell_index: int, timeout_s: int
    ) -> ExecuteResult:
        self._require(notebook_id)
        await self._bootstrap_helpers()
        cells = self._notebook.cells
        if not (0 <= cell_index < len(cells)):
            raise IndexError(f"cell_index {cell_index} out of range [0,{len(cells)})")
        cell = cells[cell_index]
        if cell.get("cell_type") != "code":
            return ExecuteResult(
                outputs=[],
                status="ok",
                execution_count=None,
                wall_time_ms=0,
            )
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        self._current_cell_index = cell_index
        try:
            result = await self._execute_internal(
                source, timeout_s=timeout_s, silent=False, store_history=True
            )
        finally:
            self._current_cell_index = None
        # nbformat.write requires NotebookNode-shaped outputs (attribute
        # access), not the raw dicts our ExecutionState produces.
        cell["outputs"] = nb.to_outputs(result.outputs)
        cell["execution_count"] = result.execution_count
        self._notebook_dirty = True
        self._maybe_persist()
        return result

    async def execute_code(
        self,
        notebook_id: str,
        code: str,
        timeout_s: int,
        silent: bool = False,
    ) -> ExecuteResult:
        self._require(notebook_id)
        await self._bootstrap_helpers()
        return await self._execute_internal(
            code, timeout_s=timeout_s, silent=silent, store_history=False
        )

    async def cancel(self, notebook_id: str) -> dict[str, Any]:
        self._require(notebook_id)
        assert self._km is not None
        was_busy = self._lock.locked()
        await self._km.interrupt_kernel()
        return {"interrupted": True, "was_busy": was_busy}

    async def close(self) -> None:
        if self._kc is not None:
            with contextlib.suppress(Exception):
                self._kc.stop_channels()
            self._kc = None
        if self._km is not None:
            with contextlib.suppress(Exception):
                await self._km.shutdown_kernel(now=False)
            self._km = None
        self._maybe_persist(force=True)

    # ---------- helpers ----------

    def get_last_plot(self) -> dict[str, Any] | None:
        return dict(self._last_plot) if self._last_plot else None

    def get_last_error(self) -> dict[str, Any] | None:
        if self._last_error is None:
            return None
        out = dict(self._last_error)
        if self._last_error_cell is not None:
            out["cell_index"] = self._last_error_cell
        return out

    def _require(self, notebook_id: str) -> None:
        if notebook_id != _NOTEBOOK_ID:
            raise ValueError(
                f"standalone mode has a single notebook 'local'; got '{notebook_id}'"
            )
        if self._notebook is None or self._km is None:
            raise RuntimeError("StandaloneSession not started")

    def _maybe_persist(self, force: bool = False) -> None:
        if self._notebook_path is None or not self._notebook_dirty:
            return
        if force or self._notebook_dirty:
            nb.write_notebook(self._notebook, self._notebook_path)
            self._notebook_dirty = False
