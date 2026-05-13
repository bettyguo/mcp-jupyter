"""kernel.list_variables — names + types + sizes, NEVER values. docs/tools.md #7."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..helpers.bootstrap import helper_call

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from ..jupyter.session import KernelSession


def register(mcp: FastMCP, session: KernelSession) -> None:
    @mcp.tool(
        name="kernel.list_variables",
        description=(
            "List user-defined variables in the kernel — names, types, sizes, "
            "shapes only. NEVER returns values. Use this to discover what's "
            "in the kernel before calling inspect on something specific. "
            "Filters out builtins and IPython internals."
        ),
    )
    async def list_variables(notebook_id: str) -> list[dict[str, Any]]:
        code = helper_call("list_variables")
        # silent=False so the helper's print(json) reaches us via stream output.
        # store_history=False keeps it out of the user's In/Out history.
        result = await session.execute_code(notebook_id, code, timeout_s=10, silent=False)
        return _parse_helper_output(result.outputs)


def _parse_helper_output(outputs: list[dict[str, Any]]) -> Any:
    """Find the last stream/stdout JSON line. M2-onward callers reuse this."""
    for out in reversed(outputs):
        if out.get("name") == "stdout" and out.get("text"):
            try:
                return json.loads(out["text"].strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                continue
    return None
