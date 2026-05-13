"""notebooks.list_open — find currently-open notebooks. See docs/tools.md #1."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="notebooks.list_open",
        description=(
            "List notebooks currently open in the Jupyter session. Use this "
            "first to find the notebook_id you'll pass to other tools. In "
            "standalone mode returns a single entry for the attached notebook."
        ),
    )
    async def list_open() -> list[dict[str, Any]]:
        handles = await session.list_notebooks()
        return [
            {
                "notebook_id": h.notebook_id,
                "path": h.path,
                "kernel_id": h.kernel_id,
                "kernel_status": h.kernel_status,
                "last_activity": h.last_activity,
            }
            for h in handles
        ]
