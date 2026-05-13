# Contributing to mcp-jupyter-kernel

Thanks for considering a contribution! This is a small, focused project — the differentiation is kernel introspection + standalone mode + a lean tool surface. Patches that hit those targets are warmly welcomed.

## Quick start

```bash
git clone https://github.com/<...>/mcp-jupyter-kernel
cd mcp-jupyter-kernel
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,data]"
pytest tests/                                       # ~50 tests, ~80s
ruff check src tests
```

Live server tests use a real `jupyter_server`. Two ways to enable:

```bash
# Option A — auto-spawn (uses subprocess locally):
MCP_JUPYTER_AUTOSPAWN_SERVER=1 pytest tests/test_server_integration.py

# Option B — point at an external server:
JUPYTER_TEST_URL=http://localhost:8888 \
  JUPYTER_TEST_TOKEN=mysecret \
  pytest tests/test_server_integration.py
```

## What to read first

In order:

1. [STATUS.md](STATUS.md) — current phase / milestone / hours.
2. [DECISIONS.md](DECISIONS.md) — locked architectural calls. Don't undo these without a new entry.
3. [docs/tools.md](docs/tools.md) — the 10-tool surface, locked.
4. [docs/privacy.md](docs/privacy.md) and [docs/data-handling.md](docs/data-handling.md) — the privacy posture is load-bearing. Changes here need explicit discussion.
5. [docs/recon/](docs/recon/) — competitive landscape + Jupyter API findings.

## What we welcome

- **Bug fixes** with a regression test.
- **Documentation improvements** — especially around install paths and Jupyter Lab / Hub / Cursor configurations we haven't documented.
- **Plot capture for additional libraries** — bokeh, holoviews, etc. Pattern: extend `_capture_plot_from()` in [src/mcp_jupyter_kernel/jupyter/output.py](src/mcp_jupyter_kernel/jupyter/output.py).
- **Improved redactor patterns** in [src/mcp_jupyter_kernel/helpers/redact.py](src/mcp_jupyter_kernel/helpers/redact.py). PRs should include test cases for both true positives and known false positives.
- **Non-Python kernel support** for `kernel.list_variables` / `inspect` (R / Julia / Deno). Will need kernel-language-aware bootstrap snippets.
- **Performance** — especially in the WS execute path. The binary v1 subprotocol negotiation is the biggest single win available (TODO at [src/mcp_jupyter_kernel/jupyter/client.py](src/mcp_jupyter_kernel/jupyter/client.py) module docstring).

## What we are NOT looking for in v1

- **More tools.** The 10-tool surface is locked. Proposals to add tools need a clear case for displacing one of the 10. See [docs/tools.md](docs/tools.md) for the rejected list and reasons.
- **Cell-CRUD parity with Datalayer's `jupyter-mcp-server`.** They cover that surface. We complement.
- **Auto-run-the-whole-notebook.** Hard no — see anti-pattern #3.
- **Bundling Jupyter itself.** Users bring their own.

## Code style

- Python 3.11+. Type-hint everything. Run `ruff check` before submitting.
- Default to NO comments. Add a `# why:` line when the rationale would surprise a future reader (workaround for a known bug, subtle invariant, non-obvious constraint).
- No new dependencies without a DECISIONS.md entry. Adding a dep is a real cost; weigh it against vendoring or skipping.
- For async code: use `httpx` + `websockets` (already chosen). Don't introduce a third async HTTP library.

## Testing rules

- Every PR adds tests OR explains why none are possible.
- Unit tests: mock the wire layer with `respx` (HTTP) or a `FakeWebSocket` (WS). See [tests/test_server_session.py](tests/test_server_session.py) for examples.
- Integration tests: prefer standalone mode (`@pytest.mark.integration_standalone`) over server mode — they run faster and don't depend on subprocess plumbing. Use `@pytest.mark.integration_server` only when the test exercises a path that's truly server-specific (REST endpoints, session lifecycle, RTC conflict detection).
- Privacy tests: any change that could leak data needs a "I tried to leak this and the redactor caught it" test.

## Submitting

1. Open an issue first for anything beyond a small bug fix. We can usually align in <24 hours.
2. PR title format: `area: short description`. Examples: `inspect: add bokeh support`, `auth: handle JupyterHub /user/X prefix`, `docs: clarify Windows token handling`.
3. PR body: what changed, why, how you tested.
4. Squash on merge.

## Code of conduct

Be kind. The Jupyter community is friendly and standards-driven; we follow that spirit. If something feels off, email the maintainer (see README).
