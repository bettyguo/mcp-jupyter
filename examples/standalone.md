# Standalone mode

Spawn a kernel directly. Useful for CI, sandboxed runs, and anyone who
doesn't have Lab open.

## One-liner

```bash
mcp-jupyter-kernel standalone --notebook ./my_analysis.ipynb
```

Your MCP client now talks to a fresh Python kernel and the notebook on
disk. No `jupyter lab` running anywhere. Edits via `cells.insert` and
`execute.cell` are written back to the file atomically.

## In-memory mode

```bash
mcp-jupyter-kernel standalone --kernel python3
```

Without `--notebook`, the notebook lives in memory only. State is lost
on process exit.

## CI

```yaml
- name: Run notebook through agent
  run: |
    mcp-jupyter-kernel standalone --notebook ./report.ipynb --transport http --port 8765 &
    # ... point your CI agent at http://localhost:8765 ...
```
