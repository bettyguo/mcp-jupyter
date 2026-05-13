"""FastMCP server entry — wires the KernelSession to the 10 v1 tools.

Used by both `mcp-jupyter-kernel serve` (server mode) and `mcp-jupyter-kernel
standalone` (standalone mode). The transport differs but the tools are the
same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import Config
from .tools import register_all

if TYPE_CHECKING:
    from .jupyter.session import KernelSession


def build_mcp(cfg: Config, session: KernelSession) -> object:
    """Construct a FastMCP server with all 10 tools registered on `session`."""
    from fastmcp import FastMCP

    mcp = FastMCP(name="mcp-jupyter-kernel")
    register_all(mcp, session)
    return mcp


async def run_server_mode(cfg: Config, token_override: str | None = None) -> None:
    from .jupyter.client import ServerSession

    session = ServerSession(cfg.jupyter, token_override=token_override)
    mcp = build_mcp(cfg, session)
    try:
        await _serve(mcp, cfg)
    finally:
        await session.close()


async def run_standalone_mode(cfg: Config) -> None:
    from .jupyter.standalone import StandaloneSession

    session = StandaloneSession(cfg.standalone)
    await session.start()
    mcp = build_mcp(cfg, session)
    try:
        await _serve(mcp, cfg)
    finally:
        await session.close()


async def _serve(mcp: object, cfg: Config) -> None:
    if cfg.server.transport == "stdio":
        await mcp.run_stdio_async()  # type: ignore[attr-defined]
    else:
        await mcp.run_http_async(host=cfg.server.host, port=cfg.server.port)  # type: ignore[attr-defined]
