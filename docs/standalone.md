# Standalone-mode design

> No Jupyter server in the loop. mcp-jupyter-kernel spawns a kernel as a subprocess via `jupyter_client` and exposes the same 10 tools as in server mode. This is half the project's value — headless CI / sandbox / ephemeral Claude Code sessions.

## CLI

```
mcp-jupyter-kernel standalone [OPTIONS]

Options:
  --notebook PATH       Path to a .ipynb to load as the working notebook.
                        If omitted, an in-memory blank notebook is created.
  --kernel NAME         Kernel name (default: python3).
  --cwd PATH            Kernel working directory (default: cwd of mcp-jupyter-kernel).
  --transport stdio|http  MCP transport (default: stdio).
  --host HOST           HTTP transport bind host (default: 127.0.0.1).
  --port INT            HTTP transport port (default: 8765).
  --audit-log PATH      Enable audit logging.
```

## Lifecycle

1. **Start.** mcp-jupyter-kernel spawns a kernel via `jupyter_client.manager.AsyncKernelManager(kernel_name=...)`. Optionally loads `--notebook` into an in-memory `nbformat.NotebookNode`.
2. **Serve.** FastMCP routes tool calls to handlers. Handlers share a single `KernelSession` instance.
3. **Shutdown.** SIGINT / SIGTERM: cancel any running cell, `await km.shutdown_kernel(now=False)`, write back the notebook to disk if `--notebook` was provided AND any cells were modified.

## Single-notebook simplification

Standalone mode has exactly one notebook and one kernel. `notebook_id` is always `"local"`. `notebooks.list_open()` returns `[{notebook_id: "local", path: <path-or-null>, kernel_id: <uuid>, kernel_status: ...}]`.

This is a deliberate simplification — multi-notebook standalone mode is post-v1.

## Persistence

If `--notebook PATH` is provided:

- On startup: GET the file, parse via `nbformat.read`, validate.
- On `cells.insert` / `execute.cell`: update the in-memory notebook AND write to disk via `nbformat.write` (atomic via `tempfile` + rename).
- On shutdown: final write if the notebook is dirty.

If no `--notebook`: notebook is in-memory only. Lost on shutdown. Useful for purely-exploratory sessions.

## Kernel output handling

The standalone-mode iopub loop mirrors the server-mode loop:

```python
while True:
    msg = await kc.get_iopub_msg(timeout=remaining_timeout)
    if msg["parent_header"].get("msg_id") != current_msg_id:
        continue
    t, c = msg["msg_type"], msg["content"]
    if t == "status" and c["execution_state"] == "idle":
        # Wait for execute_reply too — see Jupyter API recon §2.
        break
    elif t == "stream":         collect_stream(c)
    elif t == "execute_result": collect_result(c)
    elif t == "display_data":   collect_display(c)
    elif t == "error":          collect_error(c)
reply = await kc.get_shell_msg(timeout=remaining_timeout)
```

The completion condition is **both** `status:idle` on iopub AND `execute_reply` on shell with matching `parent_header.msg_id` — either alone is unsafe.

## What standalone mode does NOT do

- **No `notebooks.list_open` of files on disk.** The user passes `--notebook` to choose one. We're not a file browser.
- **No JupyterLab UI.** That's the user's separate concern.
- **No iopub rate limit.** Direct `jupyter_client` doesn't go through `jupyter_server`'s rate limiter — large outputs flow uninterrupted. Documented as a behavioral difference vs server mode.
- **No widget protocol.** ipywidgets need a `comm` partner — standalone mode doesn't provide one. Widget cells silently produce no display output. Documented limitation.

## Why this mode is worth a third of M4's budget

Without standalone mode, mcp-jupyter-kernel only works when the user has Lab open. That excludes:

- CI / GitHub Actions executing notebooks as part of test pipelines.
- Sandboxed Claude Code sessions that want to run a notebook without spinning up Lab.
- Codex / VS Code Agent ephemeral runs.
- Users who never used Lab — they have a `.ipynb` and want an agent to run it.

These collectively are a large fraction of the addressable market and zero competitors serve them well.
