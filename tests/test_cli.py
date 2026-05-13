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


def test_mcp_install_with_token_env_warns_about_inheritance(
    tmp_path, monkeypatch
) -> None:
    """Regression for S-3: --token-env reads from os.environ at runtime,
    but MCP clients (Claude Desktop, Cursor) spawn the binary with a restricted
    environment. Silent auth failure on first agent call. Install command
    should warn the user.
    """
    from mcp_jupyter_kernel import install as install_mod

    out_path = tmp_path / "test.json"
    monkeypatch.setattr(
        install_mod,
        "KNOWN_TARGETS",
        {
            "cursor": lambda: install_mod.InstallTarget(
                "cursor", out_path, "Cursor (test)"
            )
        },
    )
    r = runner.invoke(
        app,
        [
            "mcp",
            "install",
            "--client",
            "cursor",
            "--mode",
            "server",
            "--jupyter-url",
            "http://localhost:8888",
            "--token-env",
            "JUPYTER_TOKEN",
        ],
    )
    assert r.exit_code == 0
    # The warning should mention that the MCP client may not inherit env vars.
    combined = (r.stdout or "") + (r.stderr or "")
    assert "JUPYTER_TOKEN" in combined
    assert "env" in combined.lower() or "environment" in combined.lower()


def test_mcp_install_all_exits_nonzero_when_any_target_fails(
    tmp_path, monkeypatch
) -> None:
    """Regression for C-3: `mcp install --client all` previously swallowed
    per-target failures and still exited 0. Now any target failure → exit 1.

    Note on isolation: env-var monkeypatching is insufficient because
    Path.home() on Windows uses USERPROFILE / HOMEDRIVE, not HOME. We swap
    KNOWN_TARGETS directly so every path lands under tmp_path.
    """
    from mcp_jupyter_kernel import install as install_mod

    bad_path = tmp_path / "bad" / "config.json"
    good1 = tmp_path / "good1" / "config.json"
    good2 = tmp_path / "good2" / "config.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("not valid json {{{", encoding="utf-8")

    fake_targets = {
        "claude-desktop": lambda: install_mod.InstallTarget(
            "claude-desktop", bad_path, "Claude Desktop (test)"
        ),
        "cursor": lambda: install_mod.InstallTarget("cursor", good1, "Cursor (test)"),
        "cline": lambda: install_mod.InstallTarget("cline", good2, "Cline (test)"),
    }
    monkeypatch.setattr(install_mod, "KNOWN_TARGETS", fake_targets)

    r = runner.invoke(
        app,
        [
            "mcp",
            "install",
            "--client",
            "all",
            "--mode",
            "server",
            "--jupyter-url",
            "http://localhost:8888",
        ],
    )
    # Cursor + Cline succeed; Claude Desktop fails. Overall: non-zero.
    assert r.exit_code != 0, (
        f"expected non-zero exit when any target fails; got {r.exit_code}\n{r.stdout}"
    )
    # Make sure the successful targets DID get written even though one failed.
    assert good1.exists()
    assert good2.exists()
