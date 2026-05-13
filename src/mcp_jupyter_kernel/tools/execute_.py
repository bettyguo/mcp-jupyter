"""execute.cell, execute.code, execute.cancel tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession

_MAX_TIMEOUT = 1800


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="execute.cell",
        description=(
            "Execute the cell at the given index against the notebook's kernel. "
            "Outputs are persisted in the notebook AND returned. Default "
            "timeout 60s; hard max 1800s. For quick one-off checks use "
            "execute.code instead — it doesn't store anything."
        ),
    )
    async def execute_cell(
        notebook_id: str, cell_index: int, timeout_s: int = 60
    ) -> dict[str, Any]:
        timeout_s = max(1, min(_MAX_TIMEOUT, timeout_s))
        r = await session.execute_cell(notebook_id, cell_index, timeout_s)
        return {
            "outputs": r.outputs,
            "status": r.status,
            "execution_count": r.execution_count,
            "wall_time_ms": r.wall_time_ms,
        }

    @mcp.tool(
        name="execute.code",
        description=(
            "Run a one-off snippet against the kernel WITHOUT adding it to the "
            "notebook. Use for quick checks, intermediate computations, or "
            "things the user shouldn't have to read later. If the user should "
            "keep the cell, use cells.insert + execute.cell instead."
        ),
    )
    async def execute_code(
        notebook_id: str, code: str, timeout_s: int = 60
    ) -> dict[str, Any]:
        timeout_s = max(1, min(_MAX_TIMEOUT, timeout_s))
        r = await session.execute_code(notebook_id, code, timeout_s, silent=False)
        return {
            "outputs": r.outputs,
            "status": r.status,
            "wall_time_ms": r.wall_time_ms,
        }

    @mcp.tool(
        name="execute.cancel",
        description=(
            "Interrupt the currently-running cell (SIGINT-equivalent). Use "
            "when execute.cell or execute.code timed out, or when the agent "
            "realizes it kicked off something that shouldn't run to completion."
        ),
    )
    async def execute_cancel(notebook_id: str) -> dict[str, Any]:
        return await session.cancel(notebook_id)
