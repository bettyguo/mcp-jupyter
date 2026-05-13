# Jupyter server API recon

> Snapshot 2026-05-13. Practical reference for what mcp-jupyter has to speak. Source links at the bottom.

## 1. REST endpoints

Base URL: `http(s)://<host>:<port>/api/...`. All payloads JSON. Auth header `Authorization: token <TOKEN>` (see §3).

### `/api/contents/{path}` — files & directories

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/contents/{path}?type=&format=&content=1` | Read file or list dir |
| POST | `/api/contents/{path}` | Create untitled / copy |
| PUT | `/api/contents/{path}` | Save (upload) |
| PATCH | `/api/contents/{path}` | Rename |
| DELETE | `/api/contents/{path}` | Delete |

GET response (notebook):

```json
{
  "name": "Untitled.ipynb",
  "path": "work/Untitled.ipynb",
  "type": "notebook",
  "format": "json",
  "content": { "cells": [...], "metadata": {...}, "nbformat": 4, "nbformat_minor": 5 },
  "writable": true,
  "last_modified": "2026-05-13T12:34:56.000000Z",
  "size": 1234
}
```

PUT a notebook: send `{"type":"notebook","format":"json","content":<nb-json>}`. Do **not** stringify the notebook.

Gotchas:

- `?content=0` for cheap directory listings.
- `last_modified` is the conflict signal — re-GET before PUT or use `/api/contents/{path}/checkpoints`.
- The `hash` query param / field is newer; falls back gracefully if backend doesn't support it.

### `/api/sessions` — notebook path ↔ kernel binding

A **session** is `(name, path, type, kernel)` — the handle that ties a notebook on disk to a running kernel. A **kernel** is the bare runtime. UIs work with sessions, not raw kernels. POSTing a session whose path already has one returns the existing session — idempotent.

POST `/api/sessions`:

```json
{ "path": "work/Untitled.ipynb", "type": "notebook", "name": "Untitled.ipynb",
  "kernel": { "name": "python3" } }
```

Response 201:

```json
{ "id": "<session-uuid>", "path": "...", "type": "notebook",
  "kernel": { "id": "<kernel-uuid>", "name": "python3",
              "last_activity": "...", "execution_state": "idle", "connections": 0 } }
```

`DELETE /api/sessions/{id}` shuts down session **and its kernel**. Gotcha: deleting via `/api/kernels/{id}` leaves an orphan session → subsequent session DELETE returns 410.

### `/api/kernels` — kernel lifecycle

| Method | Path | Effect |
| --- | --- | --- |
| GET | `/api/kernels` | List `[{id, name, last_activity, execution_state, connections}]` |
| POST | `/api/kernels` | Start: `{"name":"python3","path":"optional/cwd"}` |
| GET | `/api/kernels/{id}` | Inspect |
| DELETE | `/api/kernels/{id}` | Hard stop |
| POST | `/api/kernels/{id}/interrupt` | SIGINT-equivalent |
| POST | `/api/kernels/{id}/restart` | Restart, keep id |

`execution_state` updates only as iopub status flows — may lag.

### `/api/kernelspecs`

GET returns installed kernels with `argv`, `display_name`, `language`. Read this before POSTing to `/api/kernels`.

## 2. WebSocket protocol — `/api/kernels/{id}/channels`

Single WS multiplexes all ZMQ channels (`shell`, `iopub`, `stdin`, `control`, `heartbeat`). Each frame carries a `channel` field.

Two encodings selectable via `Sec-WebSocket-Protocol`:

- **Default** — every frame is UTF-8 JSON: `{channel, header, parent_header, metadata, content, buffers}`.
- **`v1.kernel.websocket.jupyter.org`** — binary; little-endian uint64 offset table → `[channel, header, parent_header, metadata, content, buffer0, ...]`. Faster for large outputs / binary buffers.

### Message envelope (jupyter_client spec)

```python
{ "header":        {"msg_id":"<uuid>", "session":"<uuid>", "username":"u",
                    "date":"...", "msg_type":"execute_request", "version":"5.3"},
  "parent_header": {},
  "metadata":      {},
  "content":       {...},
  "buffers":       [] }
```

### Executing a cell

Send on `shell`:

```json
{ "channel":"shell",
  "header":{"msg_id":"abc-123","msg_type":"execute_request", ...},
  "parent_header":{}, "metadata":{},
  "content":{"code":"print('hi')\n2+2",
             "silent":false, "store_history":true,
             "user_expressions":{}, "allow_stdin":false,
             "stop_on_error":true} }
```

Expect on `iopub` (all with `parent_header.msg_id == "abc-123"`):

1. `status` → `{"execution_state":"busy"}`
2. `execute_input` → `{"code":"...","execution_count":N}`
3. `stream` → `{"name":"stdout","text":"hi\n"}`
4. `execute_result` → `{"execution_count":N,"data":{"text/plain":"4"},"metadata":{}}`
5. `status` → `{"execution_state":"idle"}`  ← cell is done

And on `shell`: `execute_reply` with `{"status":"ok","execution_count":N}` (or `error` + `ename`/`evalue`/`traceback`).

### Completion algorithm

A cell is finished only when **both** `execute_reply` on shell *and* `status:idle` on iopub have arrived for the parent msg_id. Either alone is unsafe — replies can arrive before the iopub flush; idle can fire before the reply is dispatched.

### Interrupt

`POST /api/kernels/{id}/interrupt` is the standard path. The `control` channel also accepts `interrupt_request` / `shutdown_request`.

## 3. Authentication

- **Token** is generated at server start, in the URL: `http://localhost:8888/?token=<hex>`. Discover via `jupyter server list`.
- Pass via header `Authorization: token <TOKEN>` (preferred), query string `?token=`, or session cookie (browser-only).
- Headless config:
  ```python
  c.ServerApp.token = "secret"
  c.ServerApp.password = ""
  c.ServerApp.disable_check_xsrf = True
  c.ServerApp.allow_origin = "*"
  c.IdentityProvider.token = "secret"   # newer key
  ```
- **XSRF**: writing endpoints want `_xsrf` cookie + header *unless* you authenticate via `Authorization: token` — using the token header bypasses XSRF.
- **JupyterHub**: each user has a server at `/user/{name}/`. All paths become `/user/{name}/api/...`. Auth is a Hub-issued token + `jupyterhub-user-{name}` cookie. `jupyter-server-proxy` is orthogonal — same prefix rules.

## 4. Python client libraries

- **`jupyter_client`** — direct ZMQ to a kernel process you own. NOT for talking to a server.
- **`httpx` + `websockets`** — lowest-friction async path for talking to a remote server.
- **`jupyter-kernel-client`** (Datalayer, actively maintained) — high-level wrapper for both REST + WS against a running server. **Big find — we should build on this rather than reimplement the wire protocol.** Repo: <https://github.com/datalayer/jupyter-kernel-client>.
- **`nbclient`** — batch-execute a notebook end-to-end. For "run the file," not for interactive streaming.
- **`papermill`** — parameterized notebook execution on `nbclient`.

## 5. Standalone kernel via `jupyter_client.AsyncKernelManager`

```python
import asyncio
from jupyter_client.manager import AsyncKernelManager

async def main():
    km = AsyncKernelManager(kernel_name="python3")
    await km.start_kernel()
    kc = km.client()
    kc.start_channels()
    await kc.wait_for_ready(timeout=30)

    msg_id = kc.execute("import time\nfor i in range(3):\n  print(i); time.sleep(0.1)\n42")

    while True:
        msg = await kc.get_iopub_msg(timeout=10)
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        t = msg["msg_type"]; c = msg["content"]
        if t == "stream":         print(c["name"], repr(c["text"]))
        elif t == "execute_result": print("result:", c["data"].get("text/plain"))
        elif t == "display_data":   print("display:", list(c["data"].keys()))
        elif t == "error":          print("ERR", c["ename"], c["evalue"])
        elif t == "status" and c["execution_state"] == "idle": break

    reply = await kc.get_shell_msg(timeout=10)
    assert reply["content"]["status"] == "ok"

    kc.stop_channels()
    await km.shutdown_kernel(now=False)

asyncio.run(main())
```

No `jupyter_server` involved. This is our standalone-mode path.

## 6. Gotchas

- **`display_data` vs `execute_result` vs `stream`**:
  - `stream` = `print` / `sys.stdout.write` / `sys.stderr.write`.
  - `execute_result` = the value of the **last expression** in the cell (triggers `Out[N]`).
  - `display_data` = explicit `IPython.display.display(obj)` calls, plus rich reprs.
  Picking the wrong one means missing print output or duplicating the final value.

- **Matplotlib inline backend** → `display_data` with a MIME bundle containing `image/png` (base64) + `text/plain`. With `%matplotlib widget` → `application/vnd.jupyter.widget-view+json`, needs ipywidgets comm protocol.

- **Plotly** → `application/vnd.plotly.v1+json` + `text/html` by default. PNG requires `kaleido` and `fig.show(renderer="png")`.

- **IOPub rate limit** — `ServerApp.iopub_msg_rate_limit` (1000 msg/s default) and `iopub_data_rate_limit` (1 MB/s default) with a 3 s window. Tight `print` loops or large image bursts silently drop iopub. **Direct `jupyter_client` use is unaffected** — only the server-mode path is at risk. Raise via `--ServerApp.iopub_data_rate_limit=1.0e10`.

- **Contents API vs RTC** — `/api/contents` is on-disk. When Lab has the notebook open with `jupyter_collaboration`, edits live in a Y-doc in memory and flush periodically. So:
  - A PUT while a user is editing can be overwritten by the Y-doc save or race their edits.
  - A GET may return stale content vs what's on the user's screen.
  - For RTC-safe writes, use the Y-doc API (`/api/yjs/...`) or refuse to PUT if `last_modified` advanced.
  - Read-then-write with `last_modified` conflict detection is the minimum bar.

## Sources

- REST spec: <https://jupyter-server.readthedocs.io/en/latest/developers/rest-api.html>
- OpenAPI source: `jupyter_server/services/api/api.yaml`
- WS protocols: <https://jupyter-server.readthedocs.io/en/latest/developers/websocket-protocols.html>
- Messaging spec: <https://jupyter-client.readthedocs.io/en/latest/messaging.html>
- Security: <https://jupyter-server.readthedocs.io/en/latest/operators/security.html>
- JupyterHub URL routing: <https://jupyterhub.readthedocs.io/en/stable/reference/urls.html>
- `jupyter-kernel-client` (high-level): <https://github.com/datalayer/jupyter-kernel-client>
- IOPub rate-limit context: <https://github.com/jupyter/notebook/issues/2287>
