# Attaching to a running Jupyter Lab

Server mode.

## Setup

Start Jupyter Lab somewhere with a known token:

```bash
jupyter lab --ServerApp.token=mysecret --no-browser
```

Then tell mcp-jupyter-kernel how to reach it:

```bash
export JUPYTER_TOKEN=mysecret
mcp-jupyter-kernel serve --url http://localhost:8888 --token-env JUPYTER_TOKEN
```

Or wire your MCP client (Claude Desktop / Cursor / Claude Code) to spawn
that same command, with `mcp-jupyter-kernel mcp install`. See
[docs/install.md](../docs/install.md).

## Sample flow

Open any notebook in Lab. In your agent client:

> Look at my open notebook. What's in `customer_df`? Suggest a few plots.

The agent typically calls:

1. `notebooks.list_open()` to find the file.
2. `cells.read_recent(n=5)` to read recent context.
3. `inspect("customer_df", mode="auto")` for shape, dtypes, head.
4. `inspect("customer_df", mode="summary")` for describe and value_counts.
5. `cells.insert(after_index=..., code=<plot code>)` and
   `execute.cell(...)` for any suggested plot.
6. `plots.capture_last()` to look at the rendered plot.
