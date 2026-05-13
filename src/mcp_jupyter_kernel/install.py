"""MCP client config writers (`mcp-jupyter-kernel mcp install`).

Supports any client that uses the canonical `{"mcpServers": {...}}` shape
(Claude Desktop, Cursor, Cline). For Claude Code we just print the
`claude mcp add` command; it doesn't read a file.

Writes are atomic (tempfile + rename), preserve existing entries, and
refuse to clobber invalid JSON.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallTarget:
    name: str
    config_path: Path
    description: str


def claude_desktop_target() -> InstallTarget:
    if sys.platform == "darwin":
        p = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA not set — cannot locate Claude Desktop config")
        p = Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        # Linux / unknown: follow XDG-ish convention; Claude Desktop on Linux is
        # rare but emerging clients put configs here.
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        p = Path(xdg) / "Claude" / "claude_desktop_config.json"
    return InstallTarget("claude-desktop", p, "Claude Desktop")


def cursor_target() -> InstallTarget:
    return InstallTarget("cursor", Path.home() / ".cursor" / "mcp.json", "Cursor")


def cline_target() -> InstallTarget:
    return InstallTarget(
        "cline",
        Path.home() / ".config" / "cline" / "mcp_settings.json",
        "Cline (continue.dev)",
    )


KNOWN_TARGETS: dict[str, callable] = {
    "claude-desktop": claude_desktop_target,
    "cursor": cursor_target,
    "cline": cline_target,
}


def build_server_entry(
    mode: str,
    binary_path: str,
    jupyter_url: str | None,
    jupyter_token_env: str | None,
    notebook: str | None,
) -> dict:
    """Build the {command, args, env} entry that goes under mcpServers[name]."""
    if mode == "server":
        args = ["serve"]
        if jupyter_url:
            args += ["--url", jupyter_url]
        if jupyter_token_env:
            args += ["--token-env", jupyter_token_env]
    elif mode == "standalone":
        args = ["standalone"]
        if notebook:
            args += ["--notebook", notebook]
    else:
        raise ValueError(f"unknown mode {mode!r}; expected server | standalone")
    entry: dict = {"command": binary_path, "args": args}
    # Pass through the user's environment for the token. Empty dict is
    # conventional in MCP configs and signals "inherit, plus these overrides."
    entry["env"] = {}
    return entry


def install_to_target(
    target: InstallTarget,
    server_name: str,
    entry: dict,
    *,
    overwrite: bool = True,
) -> Path:
    """Write `entry` into target's config at mcpServers[server_name]. Atomic."""
    cfg: dict = {}
    if target.config_path.exists():
        text = target.config_path.read_text(encoding="utf-8")
        if text.strip():
            try:
                cfg = json.loads(text)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"existing config at {target.config_path} is not valid JSON "
                    f"({e}); refusing to overwrite. Inspect and remove or fix it."
                ) from e
    if not isinstance(cfg, dict):
        raise RuntimeError(f"existing config at {target.config_path} is not a JSON object")
    servers = cfg.setdefault("mcpServers", {})
    if not overwrite and server_name in servers:
        raise RuntimeError(
            f"{server_name!r} is already configured in {target.config_path}; "
            f"pass --overwrite to replace."
        )
    servers[server_name] = entry
    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.config_path.with_suffix(target.config_path.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target.config_path)
    return target.config_path


def discover_binary() -> str:
    """Locate the installed mcp-jupyter-kernel binary.

    Prefers a PATH-resolvable name; falls back to `python -m mcp_jupyter_kernel.cli`.
    """
    found = shutil.which("mcp-jupyter-kernel")
    if found:
        return found
    return f"{sys.executable} -m mcp_jupyter_kernel.cli"


def claude_code_hint(
    server_name: str, binary: str, mode: str, jupyter_url: str | None
) -> str:
    """Hint string telling the user the `claude mcp add` command to run."""
    extras = ""
    if mode == "server" and jupyter_url:
        extras = f" -- {binary} serve --url {jupyter_url}"
    elif mode == "standalone":
        extras = f" -- {binary} standalone"
    else:
        extras = f" -- {binary} {mode}"
    return f"claude mcp add {server_name}{extras}"
