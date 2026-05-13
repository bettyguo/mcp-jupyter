"""Smoke tests — no kernel needed. These must pass on every commit."""

from __future__ import annotations


def test_package_imports() -> None:
    import mcp_jupyter_kernel

    assert mcp_jupyter_kernel.__version__


def test_config_defaults() -> None:
    from mcp_jupyter_kernel.config import Config

    cfg = Config()
    assert cfg.jupyter.url == "http://localhost:8888"
    assert cfg.privacy.head_size == 5
    assert cfg.server.transport == "stdio"


def test_config_env_interpolation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from mcp_jupyter_kernel.config import JupyterConfig

    monkeypatch.setenv("XYZ_FAKE_TOKEN", "tok-123")
    c = JupyterConfig(token="${XYZ_FAKE_TOKEN}")
    assert c.token == "tok-123"


def test_redactor_catches_common_secrets() -> None:
    from mcp_jupyter_kernel.helpers.redact import redact

    samples = [
        ("AKIAABCDEFGHIJKLMNOP", "aws_key"),
        ("sk-abcdefghijklmnopqrstuvwxyz", "llm_key"),
        ('api_key="abcdefghijklmnopqrstuvwxyz123"', "secret"),
    ]
    for s, kind in samples:
        out, n = redact(s)
        assert n >= 1
        assert kind in out


def test_truncate_below_cap_returns_unchanged() -> None:
    from mcp_jupyter_kernel.helpers.redact import truncate

    text, truncated, dropped = truncate("hello", 100)
    assert text == "hello"
    assert truncated is False
    assert dropped == 0


def test_truncate_above_cap_truncates() -> None:
    from mcp_jupyter_kernel.helpers.redact import truncate

    s = "x" * 200
    text, truncated, dropped = truncate(s, 100)
    assert truncated is True
    assert dropped == 100
    assert len(text.encode("utf-8")) <= 100


def test_nb_helpers_create_valid_notebook() -> None:
    from mcp_jupyter_kernel.jupyter import nb

    notebook = nb.new_notebook()
    notebook.cells.append(nb.new_code_cell("print('hi')"))
    import nbformat

    nbformat.validate(notebook)


def test_helper_call_emits_print() -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call

    code = helper_call("inspect_auto", "customer_df")
    assert "inspect_auto" in code
    assert "'customer_df'" in code
    assert code.startswith("print(__mjk_json.dumps(")
