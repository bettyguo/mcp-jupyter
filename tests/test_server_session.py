"""Unit tests for ServerSession REST methods. WS execution is integration-only.

Mocks the REST layer with respx so we don't need a running Jupyter server.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx


@pytest.fixture
def cfg():
    from mcp_jupyter_kernel.config import JupyterConfig

    return JupyterConfig(url="http://localhost:8888", token="tok-secret")


@pytest.fixture
async def session(cfg):
    from mcp_jupyter_kernel.jupyter.client import ServerSession

    s = ServerSession(cfg)
    try:
        yield s
    finally:
        await s.close()


# ---------- list_notebooks ----------


@respx.mock
async def test_list_notebooks_returns_notebook_sessions_only(session) -> None:
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "name": "foo.ipynb",
                    "kernel": {
                        "id": "k-1",
                        "name": "python3",
                        "execution_state": "idle",
                        "last_activity": "2026-05-13T12:00:00Z",
                    },
                },
                {
                    "id": "sess-2",
                    "type": "console",  # filtered out
                    "kernel": {"id": "k-2"},
                },
            ],
        )
    )
    handles = await session.list_notebooks()
    assert len(handles) == 1
    h = handles[0]
    assert h.notebook_id == "sess-1"
    assert h.path == "work/foo.ipynb"
    assert h.kernel_id == "k-1"
    assert h.kernel_status == "idle"


@respx.mock
async def test_list_notebooks_sends_authorization_header(session) -> None:
    route = respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(200, json=[])
    )
    await session.list_notebooks()
    request = route.calls.last.request
    assert request.headers["authorization"] == "token tok-secret"


# ---------- read_cells ----------


def _notebook_with_cells(n_cells: int) -> dict:
    return {
        "cells": [
            {
                "cell_type": "code",
                "source": f"x{i} = {i}\n",
                "outputs": [],
                "execution_count": i + 1,
                "metadata": {},
            }
            for i in range(n_cells)
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


@respx.mock
async def test_read_cells_returns_last_n(session) -> None:
    # Prime sessions cache.
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "idle"},
                }
            ],
        )
    )
    await session.list_notebooks()

    respx.get("http://localhost:8888/api/contents/work/foo.ipynb").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "foo.ipynb",
                "path": "work/foo.ipynb",
                "type": "notebook",
                "format": "json",
                "content": _notebook_with_cells(5),
                "last_modified": "2026-05-13T12:00:00Z",
            },
        )
    )

    cells = await session.read_cells("sess-1", n=3)
    assert len(cells) == 3
    assert [c["index"] for c in cells] == [2, 3, 4]
    assert cells[0]["cell_type"] == "code"
    assert cells[0]["source"] == "x2 = 2\n"
    assert cells[0]["execution_count"] == 3


# ---------- insert_cell with RTC-safe conflict detection ----------


@respx.mock
async def test_insert_cell_writes_back_via_put(session) -> None:
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "idle"},
                }
            ],
        )
    )
    await session.list_notebooks()

    # Read returns notebook with 2 cells, last_modified=A. Recheck returns same.
    nb_json = _notebook_with_cells(2)
    respx.get("http://localhost:8888/api/contents/work/foo.ipynb").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "name": "foo.ipynb",
                    "path": "work/foo.ipynb",
                    "type": "notebook",
                    "format": "json",
                    "content": nb_json,
                    "last_modified": "2026-05-13T12:00:00Z",
                },
            ),
            httpx.Response(200, json={"last_modified": "2026-05-13T12:00:00Z"}),
        ]
    )
    put_route = respx.put("http://localhost:8888/api/contents/work/foo.ipynb").mock(
        return_value=httpx.Response(200, json={"last_modified": "2026-05-13T12:00:01Z"})
    )

    new_idx = await session.insert_cell("sess-1", after_index=0, code="z = 99")
    assert new_idx == 1  # inserted after index 0 → position 1
    assert put_route.called
    sent = json.loads(put_route.calls.last.request.content.decode("utf-8"))
    assert sent["type"] == "notebook"
    assert sent["format"] == "json"
    assert len(sent["content"]["cells"]) == 3  # 2 original + 1 inserted
    assert "z = 99" in sent["content"]["cells"][1]["source"]


@respx.mock
async def test_insert_cell_refuses_on_concurrent_modification(session) -> None:
    from mcp_jupyter_kernel.jupyter.client import ConcurrentModificationError

    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "idle"},
                }
            ],
        )
    )
    await session.list_notebooks()

    # Read sees last_modified=A. Recheck sees last_modified=B → conflict.
    respx.get("http://localhost:8888/api/contents/work/foo.ipynb").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "name": "foo.ipynb",
                    "path": "work/foo.ipynb",
                    "type": "notebook",
                    "format": "json",
                    "content": _notebook_with_cells(2),
                    "last_modified": "2026-05-13T12:00:00Z",
                },
            ),
            httpx.Response(
                200, json={"last_modified": "2026-05-13T12:00:05Z"}
            ),  # ← user edited!
        ]
    )

    with pytest.raises(ConcurrentModificationError):
        await session.insert_cell("sess-1", after_index=0, code="z = 99")


# ---------- cancel ----------


@respx.mock
async def test_cancel_posts_interrupt(session) -> None:
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "busy"},
                }
            ],
        )
    )
    await session.list_notebooks()
    route = respx.post("http://localhost:8888/api/kernels/k-1/interrupt").mock(
        return_value=httpx.Response(204, text="")
    )
    result = await session.cancel("sess-1")
    assert result["interrupted"] is True
    assert route.called


# ---------- unknown notebook ----------


@respx.mock
async def test_read_cells_raises_on_unknown_notebook_id(session) -> None:
    with pytest.raises(KeyError, match="unknown notebook_id"):
        await session.read_cells("never-saw-this", n=3)


# ---------- url path quoting ----------


def test_url_path_quotes_special_chars() -> None:
    from mcp_jupyter_kernel.jupyter.client import _url_path

    assert _url_path("work/foo.ipynb") == "work/foo.ipynb"
    assert _url_path("a folder/x.ipynb") == "a%20folder/x.ipynb"
    assert _url_path("/leading/slash.ipynb") == "leading/slash.ipynb"


# ---------- WS-mocked execute_code ----------


class FakeWebSocket:
    """Scripted WebSocket — replays a fixed sequence of messages on recv()."""

    def __init__(self, scripted_responses: list[dict]) -> None:
        self.scripted = list(scripted_responses)
        self.sent: list[dict] = []

    async def send(self, msg: str | bytes) -> None:
        self.sent.append(json.loads(msg) if isinstance(msg, (str, bytes)) else msg)

    async def recv(self) -> str:
        if not self.scripted:
            # Block forever; ExecutionState completion will close the loop via timeout.
            import asyncio

            await asyncio.sleep(3600)
            raise AssertionError("unreached")
        # Bind parent_msg_id from the request we just received.
        msg = self.scripted.pop(0)
        if self.sent:
            parent_id = self.sent[-1]["header"]["msg_id"]
            msg.setdefault("parent_header", {})["msg_id"] = parent_id
        return json.dumps(msg)

    async def close(self) -> None:
        pass


def _ws_messages_for_one_plus_one() -> list[dict]:
    """Canonical iopub + shell sequence for executing `1+1` and getting `2`."""
    return [
        {"channel": "iopub", "msg_type": "status", "content": {"execution_state": "busy"}},
        {
            "channel": "iopub",
            "msg_type": "execute_input",
            "content": {"code": "1+1", "execution_count": 5},
        },
        {
            "channel": "iopub",
            "msg_type": "execute_result",
            "content": {
                "execution_count": 5,
                "data": {"text/plain": "2"},
                "metadata": {},
            },
        },
        {"channel": "iopub", "msg_type": "status", "content": {"execution_state": "idle"}},
        {
            "channel": "shell",
            "msg_type": "execute_reply",
            "content": {"status": "ok", "execution_count": 5},
        },
    ]


@respx.mock
async def test_execute_code_via_mocked_ws(session) -> None:
    # Prime sessions cache.
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "idle"},
                }
            ],
        )
    )
    await session.list_notebooks()

    # Patch _ensure_ws to return our scripted fake.
    fake = FakeWebSocket(_ws_messages_for_one_plus_one())

    async def fake_ensure_ws(kernel_id: str):
        return fake

    session._ensure_ws = fake_ensure_ws  # type: ignore[method-assign]

    result = await session.execute_code("sess-1", code="1+1", timeout_s=5)
    assert result.status == "ok"
    assert result.execution_count == 5
    result_outs = [o for o in result.outputs if o["output_type"] == "execute_result"]
    assert result_outs
    assert result_outs[-1]["data"].get("text/plain") == "2"

    # Verify the request we sent had the expected shape.
    assert len(fake.sent) == 1
    req = fake.sent[0]
    assert req["channel"] == "shell"
    assert req["header"]["msg_type"] == "execute_request"
    assert req["content"]["code"] == "1+1"
    assert req["content"]["silent"] is False
    assert req["content"]["store_history"] is False
    assert req["content"]["allow_stdin"] is False


@respx.mock
async def test_execute_code_error_status_propagates(session) -> None:
    respx.get("http://localhost:8888/api/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "sess-1",
                    "type": "notebook",
                    "path": "work/foo.ipynb",
                    "kernel": {"id": "k-1", "execution_state": "idle"},
                }
            ],
        )
    )
    await session.list_notebooks()

    error_seq = [
        {"channel": "iopub", "msg_type": "status", "content": {"execution_state": "busy"}},
        {
            "channel": "iopub",
            "msg_type": "execute_input",
            "content": {"code": "1/0", "execution_count": 1},
        },
        {
            "channel": "iopub",
            "msg_type": "error",
            "content": {
                "ename": "ZeroDivisionError",
                "evalue": "division by zero",
                "traceback": ["..."],
            },
        },
        {"channel": "iopub", "msg_type": "status", "content": {"execution_state": "idle"}},
        {
            "channel": "shell",
            "msg_type": "execute_reply",
            "content": {"status": "error", "ename": "ZeroDivisionError"},
        },
    ]
    fake = FakeWebSocket(error_seq)

    async def fake_ensure_ws(kernel_id: str):
        return fake

    session._ensure_ws = fake_ensure_ws  # type: ignore[method-assign]

    result = await session.execute_code("sess-1", code="1/0", timeout_s=5)
    assert result.status == "error"
    err = session.get_last_error()
    assert err is not None
    assert err["ename"] == "ZeroDivisionError"
