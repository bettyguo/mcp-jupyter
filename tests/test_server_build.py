"""Smoke tests for the full FastMCP server build.

Verifies that build_mcp(cfg, session) wires all 10 tools without import-cycle
issues or signature mismatches. Uses a fake KernelSession.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcp_jupyter_kernel.config import Config
from mcp_jupyter_kernel.jupyter.session import (
    ExecuteResult,
    KernelSession,
    NotebookHandle,
)
from mcp_jupyter_kernel.server import build_mcp


class FakeSession(KernelSession):
    """KernelSession that returns sensible defaults — used only for build smoke tests."""

    async def list_notebooks(self) -> list[NotebookHandle]:
        return []

    async def read_cells(self, notebook_id: str, n: int) -> list[dict[str, Any]]:
        return []

    async def insert_cell(self, notebook_id, after_index, code, cell_type="code") -> int:
        return 0

    async def execute_cell(self, notebook_id, cell_index, timeout_s) -> ExecuteResult:
        return ExecuteResult(outputs=[], status="ok", execution_count=1, wall_time_ms=0)

    async def execute_code(self, notebook_id, code, timeout_s, silent=False) -> ExecuteResult:
        return ExecuteResult(outputs=[], status="ok", execution_count=None, wall_time_ms=0)

    async def cancel(self, notebook_id) -> dict[str, Any]:
        return {"interrupted": True, "was_busy": False}

    async def close(self) -> None:
        pass


def test_build_mcp_succeeds() -> None:
    mcp = build_mcp(Config(), FakeSession())
    assert mcp is not None


@pytest.mark.asyncio
async def test_build_mcp_registers_all_10_tools() -> None:
    mcp = build_mcp(Config(), FakeSession())
    # FastMCP exposes tools via list_tools() (async). Verify all 10 expected
    # tool names are present.
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "notebooks.list_open",
        "cells.read_recent",
        "cells.insert",
        "execute.cell",
        "execute.code",
        "execute.cancel",
        "kernel.list_variables",
        "inspect",
        "plots.capture_last",
        "debug.last_traceback",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}; got: {names}"
