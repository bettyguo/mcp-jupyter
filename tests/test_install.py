"""Tests for the `mcp install` config-writer.

Uses tmp_path + monkeypatched config_path so we never touch real client configs.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def fake_target(tmp_path):
    from mcp_jupyter_kernel.install import InstallTarget

    return InstallTarget(
        name="claude-desktop",
        config_path=tmp_path / "claude_desktop_config.json",
        description="Claude Desktop (test)",
    )


def test_build_server_entry_server_mode() -> None:
    from mcp_jupyter_kernel.install import build_server_entry

    e = build_server_entry(
        "server", "/usr/local/bin/mcp-jupyter-kernel", "http://localhost:8888", "JUPYTER_TOKEN", None
    )
    assert e["command"] == "/usr/local/bin/mcp-jupyter-kernel"
    assert e["args"][0] == "serve"
    assert "--url" in e["args"]
    assert "--token-env" in e["args"]
    assert "http://localhost:8888" in e["args"]


def test_build_server_entry_standalone_mode_with_notebook() -> None:
    from mcp_jupyter_kernel.install import build_server_entry

    e = build_server_entry("standalone", "mcp-jupyter-kernel", None, None, "./foo.ipynb")
    assert e["args"] == ["standalone", "--notebook", "./foo.ipynb"]


def test_build_server_entry_rejects_unknown_mode() -> None:
    from mcp_jupyter_kernel.install import build_server_entry

    with pytest.raises(ValueError, match="unknown mode"):
        build_server_entry("not-a-real-mode", "x", None, None, None)


def test_install_creates_config_file_when_missing(fake_target) -> None:
    from mcp_jupyter_kernel.install import install_to_target

    entry = {"command": "x", "args": ["serve"], "env": {}}
    written = install_to_target(fake_target, "mcp-jupyter-kernel", entry)
    assert written.exists()
    parsed = json.loads(written.read_text())
    assert parsed["mcpServers"]["mcp-jupyter-kernel"] == entry


def test_install_preserves_other_mcp_servers(fake_target) -> None:
    from mcp_jupyter_kernel.install import install_to_target

    fake_target.config_path.write_text(
        json.dumps({"mcpServers": {"other-server": {"command": "y", "args": []}}})
    )
    entry = {"command": "x", "args": ["serve"], "env": {}}
    install_to_target(fake_target, "mcp-jupyter-kernel", entry)
    parsed = json.loads(fake_target.config_path.read_text())
    assert "other-server" in parsed["mcpServers"]
    assert "mcp-jupyter-kernel" in parsed["mcpServers"]


def test_install_preserves_non_mcp_keys(fake_target) -> None:
    """Claude Desktop's config has more than just mcpServers; don't clobber it."""
    from mcp_jupyter_kernel.install import install_to_target

    fake_target.config_path.write_text(
        json.dumps({"theme": "dark", "fontSize": 14, "mcpServers": {}})
    )
    install_to_target(fake_target, "x", {"command": "y", "args": [], "env": {}})
    parsed = json.loads(fake_target.config_path.read_text())
    assert parsed["theme"] == "dark"
    assert parsed["fontSize"] == 14


def test_install_refuses_to_overwrite_invalid_json(fake_target) -> None:
    from mcp_jupyter_kernel.install import install_to_target

    fake_target.config_path.write_text("not json {{{")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        install_to_target(fake_target, "x", {"command": "y", "args": [], "env": {}})


def test_install_refuses_overwrite_when_flag_unset(fake_target) -> None:
    from mcp_jupyter_kernel.install import install_to_target

    fake_target.config_path.write_text(
        json.dumps({"mcpServers": {"mcp-jupyter-kernel": {"command": "old", "args": []}}})
    )
    with pytest.raises(RuntimeError, match="already configured"):
        install_to_target(
            fake_target,
            "mcp-jupyter-kernel",
            {"command": "new", "args": [], "env": {}},
            overwrite=False,
        )


def test_install_atomic_via_tempfile(fake_target) -> None:
    from mcp_jupyter_kernel.install import install_to_target

    install_to_target(
        fake_target, "x", {"command": "y", "args": [], "env": {}}
    )
    # The tmp suffix should NOT linger after install.
    siblings = list(fake_target.config_path.parent.iterdir())
    assert all(not s.name.endswith(".tmp") for s in siblings)


def test_claude_code_hint_includes_binary_and_mode() -> None:
    from mcp_jupyter_kernel.install import claude_code_hint

    hint = claude_code_hint("mcp-jupyter-kernel", "/bin/mjk", "server", "http://x:8888")
    assert "claude mcp add" in hint
    assert "mcp-jupyter-kernel" in hint
    assert "/bin/mjk" in hint
    assert "serve" in hint
    assert "http://x:8888" in hint


def test_known_targets_contains_expected_clients() -> None:
    from mcp_jupyter_kernel.install import KNOWN_TARGETS

    assert "claude-desktop" in KNOWN_TARGETS
    assert "cursor" in KNOWN_TARGETS
    assert "cline" in KNOWN_TARGETS
    # Spot-check each target generates a sensible path.
    for name, factory in KNOWN_TARGETS.items():
        t = factory()
        assert t.name == name
        assert str(t.config_path).endswith((".json",))
