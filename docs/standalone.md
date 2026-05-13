# Standalone mode

No Jupyter server in the loop. The MCP server spawns a kernel subprocess
via `jupyter_client` and exposes the same tool surface as server mode.

Useful for headless CI runs, sandboxed agent sessions, and anyone who
has a `.ipynb` but isn't running Lab.

## CLI

```
mcp-jupyter-kernel standalone [OPTIONS]

  --notebook PATH        .ipynb to load. If omitted, an in-memory blank
                         notebook is created.
  --kernel NAME          Kernel name (default: python3).
  --cwd PATH             Kernel working directory.
  --transport stdio|http MCP transport (default: stdio).
```

## Lifecycle

- **Start.** Spawns a kernel via `AsyncKernelManager(kernel_name=...)`.
  If `--notebook` was passed, reads and validates it via `nbformat`.
- **Serve.** FastMCP routes tool calls to handlers; handlers share one
  `KernelSession` instance.
- **Shutdown.** On SIGINT / SIGTERM: shut down the kernel, write the
  notebook back to disk if `--notebook` was set and any cells were
  modified.

## Single-notebook simplification

Standalone mode has exactly one notebook and one kernel. `notebook_id`
is always `"local"`. Multi-notebook standalone is not in this version.

## Persistence

With `--notebook PATH`:

- Read on startup via `nbformat.read`, validate.
- On `cells.insert` and `execute.cell`: update the in-memory notebook
  and write to disk via `nbformat.write` (atomic via tempfile + rename).
- Final write on shutdown if the notebook is dirty.

Without `--notebook`: notebook lives in memory only and is lost on
shutdown.

## Completion semantics

A cell is finished only when **both** of these have arrived for the
matching `parent_header.msg_id`:

- `status: idle` on iopub
- `execute_reply` on shell

Either alone is unsafe: a reply can arrive before the iopub flush, and
idle can fire before the reply is dispatched. The collector lives in
`jupyter/output.py` and is shared with server mode.

## What standalone mode does not do

- Browse the filesystem for notebooks. Pass `--notebook` explicitly.
- Provide a JupyterLab UI.
- Apply the iopub rate limit. Direct `jupyter_client` doesn't go through
  `jupyter_server`'s rate limiter, so large outputs flow without
  truncation; this differs from server mode.
- Run ipywidgets. Widgets need a `comm` partner; standalone mode doesn't
  provide one. Widget cells produce no display output.
