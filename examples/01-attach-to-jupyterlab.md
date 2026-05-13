# Example 01 — Attach to a running Jupyter Lab

> Server mode. Status: walkthrough drafted; commands will be runnable from M5 onward.

## Setup

1. Start Jupyter Lab in one terminal:

   ```bash
   jupyter lab --ServerApp.token=mysecret --no-browser
   ```

2. Tell `mcp-jupyter-kernel` how to reach it:

   ```bash
   export JUPYTER_TOKEN=mysecret
   mcp-jupyter-kernel serve --url http://localhost:8888 --token-env JUPYTER_TOKEN
   ```

3. Configure your MCP client (Claude Code, Cursor, Codex) to spawn the
   command above. See [docs/install.md](../docs/install.md) (TBD M5).

## Killer-demo run-through

Open any notebook in Lab. Then in your agent client:

> "Look at my open notebook. What's in `customer_df`? Suggest 3 plots."

The agent will:

1. `notebooks.list_open` → finds your file.
2. `cells.read_recent(n=5)` → reads recent context.
3. `inspect(target="customer_df", mode="auto")` → gets shape, dtypes, head.
4. `inspect(target="customer_df", mode="summary")` → gets describe + value_counts.
5. Suggests 3 plots.
6. Optionally: `cells.insert(after_index=10, code="<plot code>")` then `execute.cell(11)`.
7. `plots.capture_last()` → looks at the rendered plot and comments.

Total wall time target: under 30 seconds.
