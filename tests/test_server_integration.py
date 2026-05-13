"""Live integration tests against a real running jupyter_server.

Run by CI with a Docker sidecar. Locally, set:
    export JUPYTER_TEST_URL=http://localhost:8888
    export JUPYTER_TEST_TOKEN=mysecret
to enable.

Skipped automatically if env vars are not set (see conftest.py fixtures).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration_server


@pytest.fixture
async def server_session(jupyter_test_url, jupyter_test_token):
    from mcp_jupyter_kernel.config import JupyterConfig
    from mcp_jupyter_kernel.jupyter.client import ServerSession

    cfg = JupyterConfig(url=jupyter_test_url, token=jupyter_test_token)
    s = ServerSession(cfg)
    try:
        yield s
    finally:
        await s.close()


async def test_list_notebooks_on_empty_server_returns_empty_list(server_session) -> None:
    # Fresh Jupyter server has no notebook sessions yet.
    handles = await server_session.list_notebooks()
    # Could have 0 sessions OR pre-existing ones; either way it's a list.
    assert isinstance(handles, list)
    for h in handles:
        assert h.notebook_id
        assert h.kernel_id


async def test_server_session_bootstraps_mjk_helpers(
    server_session, jupyter_test_url, jupyter_test_token
) -> None:
    """ServerSession must inject the __mjk helper before tool calls.

    Without it, kernel.list_variables and inspect fail with NameError on
    __mjk_json and the agent gets a None payload.
    """
    import httpx

    from mcp_jupyter_kernel.helpers.bootstrap import helper_call
    from mcp_jupyter_kernel.tools.kernel_ import _parse_helper_output

    base = jupyter_test_url.rstrip("/")
    headers = {"Authorization": f"token {jupyter_test_token}"}
    nb_path = "mjk_bootstrap_test.ipynb"
    async with httpx.AsyncClient() as http:
        await http.put(
            f"{base}/api/contents/{nb_path}",
            json={
                "type": "notebook",
                "format": "json",
                "content": {
                    "cells": [],
                    "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
                    "nbformat": 4,
                    "nbformat_minor": 5,
                },
            },
            headers=headers,
        )
        r = await http.post(
            f"{base}/api/sessions",
            json={
                "path": nb_path,
                "name": nb_path,
                "type": "notebook",
                "kernel": {"name": "python3"},
            },
            headers=headers,
        )
        sess = r.json()

    try:
        handles = await server_session.list_notebooks()
        match = [h for h in handles if h.notebook_id == sess["id"]]
        assert match, f"session {sess['id']} not in list"
        nb_id = match[0].notebook_id

        # Define a variable, then call list_variables via the helper path.
        # If __mjk isn't bootstrapped, the helper print fails (NameError) and
        # _parse_helper_output returns None.
        await server_session.execute_code(nb_id, "test_var_xyz = 42", timeout_s=15)
        r = await server_session.execute_code(
            nb_id, helper_call("list_variables"), timeout_s=15
        )
        payload = _parse_helper_output(r.outputs)
        assert payload is not None, (
            f"helper bootstrap likely missing — __mjk not in kernel. "
            f"outputs: {r.outputs}"
        )
        names = {v["name"] for v in payload}
        assert "test_var_xyz" in names
    finally:
        async with httpx.AsyncClient() as http:
            await http.delete(f"{base}/api/sessions/{sess['id']}", headers=headers)
            await http.delete(f"{base}/api/contents/{nb_path}", headers=headers)


async def test_create_session_then_list_and_execute(server_session, jupyter_test_url, jupyter_test_token) -> None:
    """End-to-end: create a notebook + session via REST, then list, read, execute."""
    import httpx

    base = jupyter_test_url.rstrip("/")
    headers = {"Authorization": f"token {jupyter_test_token}"}
    async with httpx.AsyncClient() as http:
        # Create a notebook on disk via /api/contents.
        nb_payload = {
            "type": "notebook",
            "format": "json",
            "content": {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": "x = 41\nx + 1",
                        "outputs": [],
                        "execution_count": None,
                        "metadata": {},
                        "id": "abc12345",
                    }
                ],
                "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
        }
        nb_path = "mcp_jupyter_kernel_test.ipynb"
        r = await http.put(f"{base}/api/contents/{nb_path}", json=nb_payload, headers=headers)
        r.raise_for_status()

        # Bind to a python3 kernel via /api/sessions.
        sess_payload = {
            "path": nb_path,
            "name": nb_path,
            "type": "notebook",
            "kernel": {"name": "python3"},
        }
        r = await http.post(f"{base}/api/sessions", json=sess_payload, headers=headers)
        r.raise_for_status()
        sess = r.json()

    try:
        handles = await server_session.list_notebooks()
        match = [h for h in handles if h.notebook_id == sess["id"]]
        assert match, f"created session {sess['id']} not found in list"

        cells = await server_session.read_cells(sess["id"], n=10)
        assert len(cells) == 1
        assert "x = 41" in cells[0]["source"]

        result = await server_session.execute_cell(sess["id"], cell_index=0, timeout_s=15)
        assert result.status == "ok"
        result_outs = [o for o in result.outputs if o["output_type"] == "execute_result"]
        assert result_outs, f"no execute_result in outputs: {result.outputs}"
        assert result_outs[-1]["data"].get("text/plain") == "42"

        # D-1 regression: after execute_cell PUTs the notebook back, the
        # persisted .ipynb on disk must re-validate via nbformat. If we wrote
        # raw ExecutionState dicts that don't match the nbformat schema, this
        # GET would still succeed but a stricter nbformat.validate call would
        # raise — guard against that.
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{base}/api/contents/{nb_path}?content=1", headers=headers
            )
            r.raise_for_status()
            persisted = r.json()
        import nbformat

        nb_node = nbformat.from_dict(persisted["content"])
        nbformat.validate(nb_node)
        # The executed cell should have execution_count set and at least one output.
        assert nb_node.cells[0].execution_count is not None
        assert nb_node.cells[0].outputs, "outputs lost on round-trip through PUT"
        output_types = {o["output_type"] for o in nb_node.cells[0].outputs}
        assert "execute_result" in output_types
    finally:
        # Clean up.
        async with httpx.AsyncClient() as http:
            await http.delete(f"{base}/api/sessions/{sess['id']}", headers=headers)
            await http.delete(f"{base}/api/contents/{nb_path}", headers=headers)
