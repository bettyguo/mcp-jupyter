# mcp-jupyter

An [MCP](https://modelcontextprotocol.io) server that surfaces a live
Jupyter kernel to an agent: variables, dataframe summaries, plot images,
tracebacks. The agent sees what's in the kernel, not just the `.ipynb`
JSON.

Pre-alpha; not on PyPI yet.

## Two modes

- **Server mode.** Attach to a running Jupyter Lab / Notebook 7 /
  JupyterHub.
- **Standalone mode.** Spawn a Python kernel directly via
  `jupyter_client`. No Jupyter server needed. Useful for CI and
  sandboxed agent runs.

Both modes expose the same tools.

## Quickstart

From source:

```bash
git clone https://github.com/bettyguo/mcp-jupyter.git
cd mcp-jupyter
pip install -e .
```

Wire it into a client:

```bash
# Claude Desktop, server mode:
export JUPYTER_TOKEN=mysecret
mcp-jupyter-kernel mcp install --client claude-desktop \
  --mode server --jupyter-url http://localhost:8888 --token-env JUPYTER_TOKEN

# Or standalone:
mcp-jupyter-kernel mcp install --client claude-desktop \
  --mode standalone --notebook /path/to/notebook.ipynb
```

Restart the client. Full install + troubleshooting:
[docs/install.md](docs/install.md).

## Tool surface

```
notebooks.list_open()
cells.read_recent(notebook_id, n)
cells.insert(notebook_id, after_index, code)
execute.cell(notebook_id, idx)        # persisted in the notebook
execute.code(notebook_id, code)       # ephemeral
execute.cancel(notebook_id)
kernel.list_variables(notebook_id)    # names + types + sizes, never values
inspect(notebook_id, target, mode)    # mode: auto | summary | value
plots.capture_last(notebook_id)       # base64 PNG
debug.last_traceback(notebook_id)
```

Schemas and behaviour in [docs/tools.md](docs/tools.md).

## Privacy

By default tools return summaries, not raw data: `df.shape`, `df.dtypes`,
`df.head(5)`, `df.describe()`. The `inspect` tool's `value` mode is the
only path to raw values and carries a warning in its description telling
the LLM to call it only when the user explicitly asks.

Full posture in [docs/privacy.md](docs/privacy.md).

## License

BSD-3-Clause.
