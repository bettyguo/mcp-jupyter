# Example 02 — Standalone mode (no Jupyter server)

> Spawn a kernel directly. Useful for CI, sandboxes, and headless agent runs.

## One-liner

```bash
mcp-jupyter-kernel standalone --notebook ./my_analysis.ipynb
```

That's it — your MCP client now talks to a fresh Python kernel and the
notebook on disk. No `jupyter lab` running anywhere. Edits via `cells.insert`
+ `execute.cell` write back to the file atomically.

## In-memory mode (no `.ipynb` on disk)

```bash
mcp-jupyter-kernel standalone --kernel python3
```

Useful when the agent just wants a kernel to talk to and doesn't care about
saving cells. State is lost when the process exits.

## CI use

```yaml
- name: Run notebook through agent
  run: |
    mcp-jupyter-kernel standalone --notebook ./report.ipynb --transport http --port 8765 &
    # ... point your CI-runner agent at http://localhost:8765 ...
```
