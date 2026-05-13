# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning will follow [SemVer](https://semver.org/) once we hit a stable
release; in pre-1.0 minor bumps may include behaviour changes.

## [Unreleased]

### Added

- Standalone mode. Spawns a Python kernel directly via
  `jupyter_client.AsyncKernelManager`. Atomic write-back to the `.ipynb`
  on disk if `--notebook` is provided.
- Server mode. REST + WebSocket against any running `jupyter_server`
  (Lab, Notebook 7, JupyterHub). RTC-safe writes via read-then-PUT with
  `last_modified` conflict detection.
- Polymorphic `inspect(target, mode)` tool. Three modes (`auto`,
  `summary`, `value`); the mode argument carries the privacy posture.
  `value` mode's description warns the LLM about sensitive data.
- `kernel.list_variables`. Returns names, types and sizes only.
- Plot capture from iopub `display_data` (matplotlib, plotly, altair),
  surfaced via `plots.capture_last`.
- Traceback capture via `debug.last_traceback`.
- `mcp-jupyter-kernel mcp install`. Atomic config writer for Claude
  Desktop (macOS / Windows / Linux), Cursor and Cline. Preserves
  existing entries and non-MCP keys; refuses to clobber invalid JSON.
  Claude Code via a printed `claude mcp add` hint.
- `mcp-jupyter-kernel health`. Pings the configured Jupyter server and
  reports auth, kernelspecs and open sessions.
- `mcp-jupyter-kernel standalone --notebook PATH` and
  `mcp-jupyter-kernel serve --url ... --token-env JUPYTER_TOKEN`.

### Privacy

- Tool returns capped at 50 KB; truncation is explicit
  (`truncated: true`).
- `head` size defaults to 5 rows.
- `kernel.list_variables` never returns values.
- Raw values reach the agent only via `inspect(target, mode='value')`,
  whose description warns the LLM.

### Not yet shipped

- The redactor (`helpers/redact.py`) exists and is unit-tested but is
  not yet wired into the tool return path.
- The audit log config field is parsed; no tool currently emits to it.
- Binary v1 WebSocket subprotocol; we use JSON framing.
- Multi-notebook standalone mode (one notebook per session today).
- Native introspection for non-Python kernels. R and Julia fall back to
  a degraded repr path.
- ipywidgets / `comm` protocol.
