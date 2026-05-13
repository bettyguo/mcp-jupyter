# Changelog

All notable changes to mcp-jupyter-kernel are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to honor [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it ships its first stable release.

## [Unreleased]

### Added

- **Standalone mode** — spawn a Python kernel directly via `jupyter_client.AsyncKernelManager`, no Jupyter server required. Same 10-tool surface as server mode. Atomic write-back to the `.ipynb` on disk if `--notebook` is provided.
- **Server mode** — REST + WebSocket against any running `jupyter_server` (Lab, Notebook 7, JupyterHub). RTC-safe writes via read-then-PUT with `last_modified` conflict detection.
- **Polymorphic `inspect(target, mode)` tool** — three modes (`auto`, `summary`, `value`) where the mode argument carries the privacy posture. The `value` mode tool description warns the LLM about sensitive data.
- **`kernel.list_variables`** — names, types, sizes only. Never returns values.
- **Plot capture** — matplotlib, plotly, and altair PNGs from iopub `display_data` rolled into a per-session ring buffer; surfaced via `plots.capture_last`.
- **Last-traceback capture** — iopub `error` messages cached and exposed via `debug.last_traceback`.
- **`mcp-jupyter-kernel mcp install`** — atomic config writer for Claude Desktop (macOS / Windows / Linux), Cursor, and Cline. Preserves existing entries and non-MCP keys; refuses to clobber invalid JSON. Claude Code support via a printed `claude mcp add` hint.
- **`mcp-jupyter-kernel health`** — pings the configured Jupyter server, reports auth status, kernelspecs, and open sessions. Setup-debug tool.
- **`mcp-jupyter-kernel standalone --notebook PATH`** — load and persist edits to an .ipynb on disk.
- **`mcp-jupyter-kernel serve --url ... --token-env JUPYTER_TOKEN`** — attach to a running Jupyter server.
- **Audit log** — opt-in JSONL log of every tool call. Schema in [docs/audit.md](docs/audit.md). Default off.
- **Heuristic secret redaction** — AWS keys, OpenAI/Anthropic-style keys, generic high-entropy tokens after `key|token|secret|password|api`-prefixed labels, JWTs. Best-effort; documented as such.
- **`examples/run_killer_demo.py`** — runnable end-to-end driver of the killer demo against a real kernel; emits a markdown transcript ([examples/killer-demo-transcript.md](examples/killer-demo-transcript.md)).

### Privacy posture

- Tool returns capped at 50 KB by default; truncation is always explicit (`truncated: true`).
- `data.head` size defaults to 5 rows; server-side max 100.
- `kernel.list_variables` returns names + types + sizes only — never values.
- Raw values reach the agent only via `inspect(target, mode='value')`, which carries an explicit warning in its tool description.

### Locked design decisions

See [DECISIONS.md](DECISIONS.md). Highlights:
- Tool surface locked at 10 (8 deferred to v1.1).
- Server-mode wire layer built directly on `httpx + websockets` (supersedes an earlier plan to use `jupyter-kernel-client`, which turned out to be sync).
- Standalone mode is first-class, not a deferred feature.
- Cell-by-cell execution only; no auto-run-the-whole-notebook in v1.

### Known limitations

- Hero GIF and live Claude Desktop / Cursor verification are pre-publish manual steps.
- Binary v1 WebSocket subprotocol (`v1.kernel.websocket.jupyter.org`) is on the roadmap as a [good-first-issue](docs/good-first-issues.md); v0 uses JSON framing.
- Single notebook in standalone mode (multi-notebook is post-v1).
- Non-Python kernels (R, Julia) fall back to a degraded `repr` path for `inspect`; first-class support is a tracked [good-first-issue](docs/good-first-issues.md).
- ipywidgets are not surfaced — needs a `comm` protocol implementation.

[Unreleased]: https://github.com/bettyguo/mcp-jupyter/compare/HEAD...HEAD
