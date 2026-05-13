"""Typer CLI. Two subcommands: `serve` (server mode) and `standalone`."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from . import __version__
from .config import Config

app = typer.Typer(
    name="mcp-jupyter-kernel",
    help="Kernel-aware MCP server for Jupyter notebooks.",
    no_args_is_help=True,
    add_completion=False,
)

mcp_app = typer.Typer(
    name="mcp",
    help="MCP client integration helpers (Claude Desktop, Cursor, Claude Code).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(mcp_app, name="mcp")


@app.command()
def version() -> None:
    """Print version and exit."""
    typer.echo(__version__)


@app.command()
def serve(
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to YAML config."),
    url: str | None = typer.Option(None, "--url", help="Jupyter server URL override."),
    token: str | None = typer.Option(None, "--token", help="Jupyter token override (avoid; use --token-env)."),
    token_env: str | None = typer.Option(None, "--token-env", help="Env var holding the token."),
    transport: str | None = typer.Option(None, "--transport", help="stdio | http"),
) -> None:
    """Run in server mode — attach to a running Jupyter server."""
    import os

    cfg = Config.load(config)
    if url:
        cfg.jupyter.url = url
    if transport:
        cfg.server.transport = transport  # type: ignore[assignment]

    resolved_token = token or (os.environ.get(token_env) if token_env else None)
    from .server import run_server_mode

    asyncio.run(run_server_mode(cfg, token_override=resolved_token))


@app.command()
def standalone(
    notebook: Path | None = typer.Option(None, "--notebook", help="Path to a .ipynb to load."),
    kernel: str = typer.Option("python3", "--kernel", help="Kernel name."),
    cwd: Path | None = typer.Option(None, "--cwd", help="Kernel working directory."),
    transport: str = typer.Option("stdio", "--transport", help="stdio | http"),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to YAML config."),
) -> None:
    """Run in standalone mode — spawn a kernel directly, no Jupyter server."""
    cfg = Config.load(config)
    cfg.standalone.kernel_name = kernel
    if cwd:
        cfg.standalone.cwd = str(cwd)
    if notebook:
        cfg.standalone.notebook_path = str(notebook)
    cfg.server.transport = transport  # type: ignore[assignment]

    from .server import run_standalone_mode

    asyncio.run(run_standalone_mode(cfg))


@app.command()
def health(
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to YAML config."),
    url: str | None = typer.Option(None, "--url", help="Jupyter URL override."),
    token: str | None = typer.Option(None, "--token", help="Token override."),
    token_env: str | None = typer.Option(None, "--token-env", help="Env var holding the token."),
) -> None:
    """Ping the configured Jupyter server and report status.

    Useful when an MCP-client install isn't working — checks auth, lists
    kernels and open sessions. Prints a one-line summary plus details.
    """
    import asyncio
    import os

    from .config import Config

    cfg = Config.load(config)
    if url:
        cfg.jupyter.url = url

    resolved_token = token or (os.environ.get(token_env) if token_env else None)

    async def _check() -> int:
        import httpx

        from .auth import auth_headers, resolve_token

        try:
            tok = resolve_token(cfg.jupyter, resolved_token)
        except Exception as e:
            typer.echo(f"[FAIL] auth: {e}", err=True)
            return 2

        base = cfg.jupyter.url.rstrip("/") + cfg.jupyter.base_url_prefix
        async with httpx.AsyncClient(
            base_url=base, headers=auth_headers(tok), timeout=10.0, verify=cfg.jupyter.verify_tls
        ) as http:
            try:
                api = await http.get("/api")
                api.raise_for_status()
            except Exception as e:
                typer.echo(f"[FAIL] could not reach {base}/api: {e}", err=True)
                return 3

            try:
                specs = (await http.get("/api/kernelspecs")).json()
            except Exception as e:
                typer.echo(f"[WARN] /api/kernelspecs: {e}")
                specs = {}

            try:
                sessions = (await http.get("/api/sessions")).json()
            except Exception as e:
                typer.echo(f"[WARN] /api/sessions: {e}")
                sessions = []

        typer.echo(f"[OK]   reachable: {base}")
        typer.echo(f"[OK]   auth: token (length {len(tok)})")
        ks = specs.get("kernelspecs") if isinstance(specs, dict) else None
        if ks:
            default = specs.get("default", "?")
            typer.echo(f"[OK]   kernelspecs: {len(ks)} installed (default: {default})")
            for name in sorted(ks):
                typer.echo(f"         - {name}")
        notebook_sessions = [s for s in sessions if s.get("type") == "notebook"]
        typer.echo(f"[OK]   open notebook sessions: {len(notebook_sessions)}")
        for s in notebook_sessions[:10]:
            kernel = s.get("kernel") or {}
            typer.echo(
                f"         - {s.get('path', '?')} (kernel={kernel.get('name', '?')}, "
                f"status={kernel.get('execution_state', '?')})"
            )
        return 0

    rc = asyncio.run(_check())
    raise typer.Exit(code=rc)


@mcp_app.command("install")
def mcp_install(
    client: str = typer.Option(
        "claude-desktop",
        "--client",
        help="claude-desktop | cursor | cline | all | claude-code (prints hint).",
    ),
    name: str = typer.Option(
        "mcp-jupyter-kernel", "--name", help="Server name in the client's mcpServers map."
    ),
    mode: str = typer.Option("server", "--mode", help="server | standalone."),
    jupyter_url: str | None = typer.Option(None, "--jupyter-url", help="Jupyter URL (server mode)."),
    jupyter_token_env: str = typer.Option(
        "JUPYTER_TOKEN", "--token-env", help="Env var the server will read the token from."
    ),
    notebook: str | None = typer.Option(None, "--notebook", help="Path to .ipynb (standalone mode)."),
    binary: str | None = typer.Option(None, "--binary", help="Override the binary path."),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite"),
) -> None:
    """Write mcp-jupyter-kernel into the specified MCP client's config."""
    from .install import (
        KNOWN_TARGETS,
        build_server_entry,
        claude_code_hint,
        discover_binary,
        install_to_target,
    )

    resolved_binary = binary or discover_binary()
    entry = build_server_entry(mode, resolved_binary, jupyter_url, jupyter_token_env, notebook)

    if client == "claude-code":
        typer.echo(claude_code_hint(name, resolved_binary, mode, jupyter_url))
        return

    targets_to_install: list[str]
    if client == "all":
        targets_to_install = list(KNOWN_TARGETS.keys())
    elif client in KNOWN_TARGETS:
        targets_to_install = [client]
    else:
        typer.echo(
            f"unknown --client {client!r}. Known: {', '.join(KNOWN_TARGETS)}, all, claude-code.",
            err=True,
        )
        raise typer.Exit(code=2)

    for tname in targets_to_install:
        target = KNOWN_TARGETS[tname]()
        try:
            written = install_to_target(target, name, entry, overwrite=overwrite)
            typer.echo(f"wrote {target.description} config: {written}")
        except Exception as e:
            typer.echo(f"  ! {target.description}: {e}", err=True)


@mcp_app.command("show")
def mcp_show(
    client: str = typer.Option("claude-desktop", "--client", help="claude-desktop | cursor | cline"),
) -> None:
    """Print where the client's config lives without writing anything."""
    from .install import KNOWN_TARGETS

    if client not in KNOWN_TARGETS:
        typer.echo(f"unknown --client {client!r}. Known: {', '.join(KNOWN_TARGETS)}.", err=True)
        raise typer.Exit(code=2)
    target = KNOWN_TARGETS[client]()
    typer.echo(f"{target.description}: {target.config_path}")
    typer.echo(f"exists: {target.config_path.exists()}")


if __name__ == "__main__":
    app()
