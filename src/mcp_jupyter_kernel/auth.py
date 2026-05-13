"""Token resolution for server mode. See docs/auth.md.

Standalone mode does not auth — the kernel is a child process of this server.
"""

from __future__ import annotations

from .config import JupyterConfig


def resolve_token(cfg: JupyterConfig, cli_override: str | None = None) -> str:
    """Resolve the Jupyter token. CLI override beats config beats env."""
    if cli_override:
        return cli_override
    if cfg.token:
        return cfg.token
    raise RuntimeError(
        "No Jupyter token configured. Set jupyter.token in config, "
        "pass --token, or set the env var the config references via ${VAR}."
    )


def auth_headers(token: str) -> dict[str, str]:
    """Header form. Using this on REST and WS bypasses XSRF entirely."""
    return {"Authorization": f"token {token}"}
