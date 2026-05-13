"""CLI smoke tests via Typer's runner."""

from __future__ import annotations

from typer.testing import CliRunner

from mcp_jupyter_kernel.cli import app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert r.stdout.strip().startswith("0.")


def test_help_lists_subcommands() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("version", "serve", "standalone", "mcp", "health"):
        assert cmd in r.stdout


def test_mcp_show_known_client(tmp_path, monkeypatch) -> None:
    # Monkeypatch HOME / APPDATA so we don't poke real user configs.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    r = runner.invoke(app, ["mcp", "show", "--client", "cursor"])
    assert r.exit_code == 0
    assert "Cursor" in r.stdout


def test_mcp_show_unknown_client_exits_2() -> None:
    r = runner.invoke(app, ["mcp", "show", "--client", "not-a-real-client"])
    assert r.exit_code == 2


def test_mcp_install_claude_code_prints_hint() -> None:
    r = runner.invoke(
        app,
        [
            "mcp",
            "install",
            "--client",
            "claude-code",
            "--mode",
            "server",
            "--jupyter-url",
            "http://localhost:8888",
        ],
    )
    assert r.exit_code == 0
    assert "claude mcp add" in r.stdout
    assert "http://localhost:8888" in r.stdout


def test_health_fails_with_no_token() -> None:
    r = runner.invoke(app, ["health", "--url", "http://localhost:8888"])
    # No token configured → resolve_token raises → health exits 2.
    assert r.exit_code == 2
