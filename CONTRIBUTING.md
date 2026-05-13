# Contributing

Patches and bug reports welcome.

## Quick start

```bash
git clone https://github.com/bettyguo/mcp-jupyter.git
cd mcp-jupyter
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,data]"
pytest tests/
ruff check src tests
```

The live server-mode tests need a real `jupyter_server`. Two ways to
enable them:

```bash
# Auto-spawn a subprocess locally:
MCP_JUPYTER_AUTOSPAWN_SERVER=1 pytest tests/test_server_integration.py

# Or point at an external server:
JUPYTER_TEST_URL=http://localhost:8888 \
  JUPYTER_TEST_TOKEN=mysecret \
  pytest tests/test_server_integration.py
```

## Useful entry points to read first

1. `docs/tools.md` for the agent-visible tool surface.
2. `docs/privacy.md` for the data-handling posture. Changes here need
   discussion.
3. `src/mcp_jupyter_kernel/jupyter/session.py` for the
   server-vs-standalone abstraction.

## Welcome contributions

- Bug fixes with a regression test.
- Documentation improvements, especially install paths and Jupyter
  Lab / Hub / Cursor configurations we haven't documented.
- Plot capture for additional libraries (bokeh, holoviews). Extension
  point: `_capture_plot_from()` in `jupyter/output.py`.
- Improved redactor patterns in `helpers/redact.py`. PRs should include
  both true-positive and known-false-positive test cases.
- Non-Python kernel support (R, Julia) for `kernel.list_variables` and
  `inspect`. Will need language-aware bootstrap snippets.
- Performance. The biggest single win on the WS path is negotiating the
  binary `v1.kernel.websocket.jupyter.org` subprotocol; today we only
  speak JSON.

## Not in scope right now

- More tools. The current surface is intentionally small. Proposals to
  add tools should explain which of the existing ones gets displaced.
- Cell-CRUD parity with Datalayer's `jupyter-mcp-server`. They cover
  that surface; we complement.
- Auto-running an entire notebook.
- Bundling Jupyter itself.

## Code style

- Python 3.11+. Type-hint public surfaces. Run `ruff check` before
  submitting.
- Comment why, not what. Inline obvious meaning into the code; a
  comment that just restates the next line should be deleted.
- Avoid adding new dependencies if it can be helped. Open an issue
  first to discuss.

## Tests

- Every PR adds tests, or explains why none are practical.
- Unit tests mock the wire layer with `respx` (HTTP) or a small
  `FakeWebSocket` (WS). See `tests/test_server_session.py`.
- Prefer `@pytest.mark.integration_standalone` over
  `@pytest.mark.integration_server` when possible; the standalone path
  has fewer moving parts.

## Submitting

1. Open an issue first if the change is non-trivial.
2. PR title: `area: short summary`. Examples: `inspect: add bokeh
   support`, `auth: handle JupyterHub /user/<name> prefix`.
3. Squash on merge.
