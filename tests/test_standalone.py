"""Integration tests for StandaloneSession against a real python3 kernel.

Marked `integration_standalone`. Spawns a kernel subprocess via jupyter_client.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration_standalone


@pytest.fixture
async def session():
    from mcp_jupyter_kernel.config import StandaloneConfig
    from mcp_jupyter_kernel.jupyter.standalone import StandaloneSession

    s = StandaloneSession(StandaloneConfig(kernel_name="python3"))
    await s.start()
    try:
        yield s
    finally:
        await s.close()


async def test_kernel_starts_and_executes_basic_code(session) -> None:
    handles = await session.list_notebooks()
    assert len(handles) == 1
    assert handles[0].notebook_id == "local"
    assert handles[0].kernel_status == "idle"

    r = await session.execute_code("local", "2 + 2", timeout_s=10)
    assert r.status == "ok"
    # Last expression → execute_result with text/plain "4"
    result_outs = [o for o in r.outputs if o["output_type"] == "execute_result"]
    assert result_outs
    assert result_outs[-1]["data"].get("text/plain") == "4"


async def test_print_captured_as_stream(session) -> None:
    r = await session.execute_code("local", "print('hello')", timeout_s=10)
    assert r.status == "ok"
    streams = [o for o in r.outputs if o["output_type"] == "stream"]
    assert streams
    assert "hello" in "".join(s["text"] for s in streams)


async def test_error_captured_in_outputs_and_last_error(session) -> None:
    r = await session.execute_code("local", "1/0", timeout_s=10)
    assert r.status == "error"
    errs = [o for o in r.outputs if o["output_type"] == "error"]
    assert errs
    assert errs[0]["ename"] == "ZeroDivisionError"

    captured = session.get_last_error()
    assert captured is not None
    assert captured["ename"] == "ZeroDivisionError"


async def test_helper_bootstrap_makes_mjk_available(session) -> None:
    # First execute_code triggers bootstrap. After that, __mjk should be in scope.
    await session.execute_code("local", "x = 1", timeout_s=10)
    r = await session.execute_code("local", "__mjk.__name__", timeout_s=10)
    assert r.status == "ok"
    result_outs = [o for o in r.outputs if o["output_type"] == "execute_result"]
    assert result_outs
    # __mjk is the _MjkHelpers class itself (so .__name__ is '_MjkHelpers').
    assert "_MjkHelpers" in result_outs[-1]["data"].get("text/plain", "")


async def test_list_variables_via_helper(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    await session.execute_code("local", "a = 42\nb = [1, 2, 3]\ns = 'hi'", timeout_s=10)
    code = helper_call("list_variables")
    # silent=False because the helper's print(json.dumps(...)) only reaches us via
    # iopub stream — and silent=True (per spec) suppresses iopub stream output.
    r = await session.execute_code("local", code, timeout_s=10, silent=False)
    payload = _parse_helper_output(r.outputs)
    assert payload is not None
    names = {v["name"] for v in payload}
    assert {"a", "b", "s"}.issubset(names)
    for v in payload:
        assert "name" in v and "type" in v
        # NEVER values
        assert "value" not in v


async def test_insert_cell_then_execute(session) -> None:
    # Standalone starts with an empty in-memory notebook.
    idx = await session.insert_cell("local", after_index=-1, code="x_inserted = 7")
    assert idx == 0
    r = await session.execute_cell("local", cell_index=idx, timeout_s=10)
    assert r.status == "ok"
    # Subsequent code can see x_inserted.
    r2 = await session.execute_code("local", "x_inserted", timeout_s=10)
    result_outs = [o for o in r2.outputs if o["output_type"] == "execute_result"]
    assert result_outs[-1]["data"].get("text/plain") == "7"


async def test_inspect_auto_on_simple_dict(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    await session.execute_code("local", "d = {'a': 1, 'b': 2, 'c': 3}", timeout_s=10)
    code = helper_call("inspect_auto", "d")
    r = await session.execute_code("local", code, timeout_s=10, silent=False)
    payload = _parse_helper_output(r.outputs)
    assert payload is not None
    assert payload["kind"] == "dict"
    assert payload["len"] == 3
    assert set(payload["key_sample"]) == {"a", "b", "c"}
