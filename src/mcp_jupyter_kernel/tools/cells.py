"""cells.read_recent and cells.insert tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="cells.read_recent",
        description=(
            "Read the most recent N cells of a notebook (default 5). Use this "
            "to ground in current context before reasoning about a notebook. "
            "For a single specific cell, pass n=1."
        ),
    )
    async def read_recent(notebook_id: str, n: int = 5) -> list[dict[str, Any]]:
        n = max(1, min(50, n))
        return await session.read_cells(notebook_id, n)

    @mcp.tool(
        name="cells.insert",
        description=(
            "Insert a new cell after the given index. Use to add agent-authored "
            "code the user should keep. In server mode, refuses if the user has "
            "edited the notebook since you last read it — re-read with "
            "cells.read_recent and retry."
        ),
    )
    async def insert(
        notebook_id: str,
        after_index: int,
        code: str,
        cell_type: str = "code",
    ) -> dict[str, Any]:
        if cell_type not in ("code", "markdown"):
            return {"error": "cell_type must be 'code' or 'markdown'"}
        try:
            new_idx = await session.insert_cell(notebook_id, after_index, code, cell_type)
        except Exception as e:
            # Surface RTC conflicts cleanly for the agent.
            from ..jupyter.client import ConcurrentModificationError

            if isinstance(e, ConcurrentModificationError):
                return {"error": "conflict", "detail": str(e)}
            raise
        return {"new_index": new_idx}
