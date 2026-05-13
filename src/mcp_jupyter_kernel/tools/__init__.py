"""MCP tool implementations. Each module registers its tools with the FastMCP
server passed in. See docs/tools.md for the locked v1 surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register_all(mcp: FastMCP, session: KernelSession) -> None:
    """Wire all v1 tools onto the FastMCP server."""
    from . import cells, debug_, execute_, inspect_, kernel_, notebooks, plots

    notebooks.register(mcp, session)
    cells.register(mcp, session)
    execute_.register(mcp, session)
    kernel_.register(mcp, session)
    inspect_.register(mcp, session)
    plots.register(mcp, session)
    debug_.register(mcp, session)
