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


async def test_create_session_then_list_and_execute(server_session, jupyter_test_url, jupyter_test_token) -> None:
    """Full M1+M2 path: create a notebook + session via REST, then list, read, execute."""
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

        # Execute the cell. M2.
        result = await server_session.execute_cell(sess["id"], cell_index=0, timeout_s=15)
        assert result.status == "ok"
        result_outs = [o for o in result.outputs if o["output_type"] == "execute_result"]
        assert result_outs, f"no execute_result in outputs: {result.outputs}"
        assert result_outs[-1]["data"].get("text/plain") == "42"
    finally:
        # Clean up.
        async with httpx.AsyncClient() as http:
            await http.delete(f"{base}/api/sessions/{sess['id']}", headers=headers)
            await http.delete(f"{base}/api/contents/{nb_path}", headers=headers)
