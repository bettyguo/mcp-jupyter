"""debug.last_traceback tool. Returns the most recent kernel error."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="debug.last_traceback",
        description=(
            "Return the most recent exception raised in the kernel with a "
            "formatted traceback. Returns null if no error has occurred since "
            "the kernel started or last reset. Use this after execute.cell or "
            "execute.code returns status='error' to get the details."
        ),
    )
    async def last_traceback(notebook_id: str) -> dict[str, Any] | None:
        return session.get_last_error()
