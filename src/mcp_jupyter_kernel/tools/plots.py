"""plots.capture_last — most recent rendered plot as base64 PNG. docs/tools.md #9.

The session tracks plot output in its iopub loop. This tool just reads the
captured state. See jupyter/output.py for the capture logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="plots.capture_last",
        description=(
            "Return the most recently rendered plot as a base64 PNG. Works "
            "for matplotlib (inline backend), plotly (requires kaleido), and "
            "altair. Returns null if no plot has been rendered since kernel "
            "start or last reset."
        ),
    )
    async def capture_last(notebook_id: str) -> dict[str, Any] | None:
        return session.get_last_plot()
