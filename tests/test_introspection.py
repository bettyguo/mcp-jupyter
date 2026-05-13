"""M3+M4 tests: inspect with multiple modes, plots, debug. Standalone-mode.

Requires pandas / numpy / matplotlib (skipped per-test if missing).
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


# ---------- inspect auto mode ----------


async def test_inspect_auto_on_ndarray(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    try:
        import numpy  # noqa: F401
    except ImportError:
        pytest.skip("numpy not installed in this kernel")

    await session.execute_code(
        "local", "import numpy as np; a = np.arange(12).reshape(3, 4)", timeout_s=10
    )
    r = await session.execute_code(
        "local", helper_call("inspect_auto", "a"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["kind"] == "ndarray"
    assert payload["shape"] == [3, 4]
    assert payload["dtype"].startswith("int")
    assert payload["head"][:3] == [0, 1, 2]


async def test_inspect_auto_on_dataframe(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    try:
        import pandas  # noqa: F401
    except ImportError:
        pytest.skip("pandas not installed in this kernel")

    await session.execute_code(
        "local",
        "import pandas as pd; df = pd.DataFrame({'x': [1,2,3], 'y': ['a','b','c']})",
        timeout_s=10,
    )
    r = await session.execute_code(
        "local", helper_call("inspect_auto", "df"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["kind"] == "dataframe"
    assert payload["shape"] == [3, 2]
    assert set(payload["columns"]) == {"x", "y"}
    assert payload["dtypes"]["x"].startswith("int")
    assert len(payload["head"]) == 3


async def test_inspect_summary_on_dataframe(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    try:
        import pandas  # noqa: F401
    except ImportError:
        pytest.skip("pandas not installed in this kernel")

    await session.execute_code(
        "local",
        "import pandas as pd; df = pd.DataFrame({'x': [1,2,3,4,5], 'cat': ['a','a','b','b','c']})",
        timeout_s=10,
    )
    r = await session.execute_code(
        "local", helper_call("inspect_summary", "df"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["kind"] == "dataframe_summary"
    assert "describe" in payload
    # 'cat' has nunique=3, ≤ 50 → value_counts captured.
    assert "cat" in payload["value_counts"]


async def test_inspect_value_returns_repr(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    await session.execute_code("local", "x = [1, 2, 3]", timeout_s=10)
    r = await session.execute_code(
        "local", helper_call("inspect_value", "x"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["repr"] == "[1, 2, 3]"
    assert payload["truncated"] is False


async def test_inspect_value_truncates_large(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    await session.execute_code("local", "big = 'x' * 100000", timeout_s=10)
    r = await session.execute_code(
        "local", helper_call("inspect_value", "big"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["truncated"] is True
    assert payload["bytes_dropped"] > 0


async def test_inspect_unknown_variable_returns_not_found(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    r = await session.execute_code(
        "local", helper_call("inspect_auto", "nonexistent_variable_xyz"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    assert payload["error"] == "not_found"


# ---------- list_variables ----------


async def test_list_variables_filters_underscores_and_builtins(session) -> None:
    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    await session.execute_code(
        "local",
        "user1 = 42\nuser2 = 'hello'\n_private = 99\nclass MyCls: pass",
        timeout_s=10,
    )
    r = await session.execute_code(
        "local", helper_call("list_variables"), timeout_s=10
    )
    payload = _parse_helper_output(r.outputs)
    names = {v["name"] for v in payload}
    assert {"user1", "user2", "MyCls"}.issubset(names)
    # Underscore-prefixed AND IPython internals filtered.
    assert "_private" not in names
    assert "_MjkHelpers" not in names
    assert "__mjk" not in names
    assert "In" not in names


# ---------- plots capture ----------


async def test_plot_capture_after_matplotlib_render(session) -> None:
    try:
        import matplotlib  # noqa: F401
        import matplotlib_inline  # noqa: F401
    except ImportError:
        pytest.skip("matplotlib or matplotlib_inline not installed")

    # %matplotlib inline installs the inline display formatter so display(fig)
    # produces a display_data message with image/png in the MIME bundle.
    code = (
        "get_ipython().run_line_magic('matplotlib', 'inline')\n"
        "import matplotlib.pyplot as plt\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot([1, 2, 3], [4, 5, 6])\n"
        "from IPython.display import display\n"
        "display(fig)\n"
        "plt.close(fig)\n"
    )
    r = await session.execute_code("local", code, timeout_s=30)
    assert r.status == "ok", f"render failed: {r.outputs}"
    plot = session.get_last_plot()
    assert plot is not None, f"no plot captured. outputs: {r.outputs}"
    assert plot["source"] == "matplotlib"
    assert plot["image_png_base64"]
    # base64 of PNG should start with 'iVBOR' (PNG magic in base64).
    assert plot["image_png_base64"].startswith("iVBOR")


# ---------- debug last_traceback ----------


async def test_last_error_captures_zero_division(session) -> None:
    r = await session.execute_code("local", "x = 1/0", timeout_s=10)
    assert r.status == "error"
    err = session.get_last_error()
    assert err is not None
    assert err["ename"] == "ZeroDivisionError"
    assert "division" in err["evalue"].lower()
    assert err["traceback"]  # non-empty list


async def test_last_error_is_none_after_clean_execution(session) -> None:
    # Fresh session: no error captured yet.
    err = session.get_last_error()
    assert err is None
    await session.execute_code("local", "y = 2 + 2", timeout_s=10)
    err = session.get_last_error()
    assert err is None
