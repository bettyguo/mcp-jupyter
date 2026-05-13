# STATUS

> Single source of truth for "where is the project right now?" Update at the end of every session.

## Snapshot

- **Current phase:** Phase 3 — Polish (~95% done). Phase 4 drafts staged.
- **Current milestone:** Hero GIF (needs a real screen recording) is the only Phase 3 deliverable that can't be produced autonomously. Everything else is in.
- **Last updated:** 2026-05-13
- **Next action:** Record the hero GIF. Then live-run a real Claude Desktop / Cursor install and verify the killer demo. Then PyPI publish + launch per `docs/launch.md`.

## Validation snapshot (this session)

```
$ python -m pytest tests/
============ 54 passed, 2 skipped, 17 warnings in 57s ============

$ MCP_JUPYTER_AUTOSPAWN_SERVER=1 python -m pytest tests/
================== 56 passed, 17 warnings in 69s ==================
                  (server-integration tests run against an
                   auto-spawned local jupyter_server)

$ python -m ruff check src tests
All checks passed!
```

- 8 smoke tests (config / redactor / nbformat / helper_call)
- 7 standalone integration tests (real Python kernel via jupyter_client)
- 10 introspection tests (inspect auto/summary/value, list_variables, plots, debug — pandas DataFrame + Series, numpy ndarray, dict, matplotlib PNG, ZeroDivisionError)
- 10 server-session tests (8 respx-mocked REST + 2 WS-mocked execute)
- 11 install-command tests (atomic writes, preserves existing servers / non-MCP keys, JSON validation, all 3 KNOWN_TARGETS)
- 6 CLI tests (Typer runner: version, help tree, mcp show, mcp install hint, health failure path)
- 2 FastMCP build smoke tests (build_mcp succeeds; all 10 tools registered)
- 2 live integration_server tests skip-by-default; activate with `MCP_JUPYTER_AUTOSPAWN_SERVER=1` (subprocess spawn) or `JUPYTER_TEST_URL` (CI / Docker).

## Headline finding — read before doing anything else

Phase 0.1 recon **invalidated the master-prompt thesis** that no production-quality Jupyter MCP server exists. Datalayer's `jupyter-mcp-server` is at ~1.1k stars, weekly commits, full CI/docs/Docker. mcp-jupyter-kernel differentiates on:

1. First-class **kernel introspection** (variables, dataframe summaries, plot capture, traceback explain).
2. **Standalone / spawn-kernel** mode for headless / CI use.
3. **Debugger-grade** tools (post-v1 stretch).
4. A **lean 10-tool surface** (locked) with strong schemas vs Datalayer's 17 and Block's 4.

Cell CRUD stays minimal — only what the killer demo requires.

Full recon: [docs/recon/competitive.md](docs/recon/competitive.md), [docs/recon/jupyter-api.md](docs/recon/jupyter-api.md). Tool surface: [docs/tools.md](docs/tools.md).

## Done

**Phase 0 — Think**

- Repo skeleton — dirs, LICENSE (BSD-3-Clause), [.gitignore](.gitignore), [README.md](README.md), [pyproject.toml](pyproject.toml).
- Phase 0.1 competitive recon → [docs/recon/competitive.md](docs/recon/competitive.md). Thesis invalidated; positioning pivoted.
- Phase 0.2 Jupyter REST/WS API recon → [docs/recon/jupyter-api.md](docs/recon/jupyter-api.md). Will build on `jupyter-kernel-client`.
- Killer-demo spec locked → [docs/killer-demo.md](docs/killer-demo.md).
- Privacy + safety design → [docs/privacy.md](docs/privacy.md).

**Phase 1 — Design**

- Project renamed to `mcp-jupyter-kernel` (PyPI dist) / `mcp_jupyter_kernel` (import).
- Tool surface locked at 10 → [docs/tools.md](docs/tools.md).
- Auth design → [docs/auth.md](docs/auth.md).
- Standalone-mode design → [docs/standalone.md](docs/standalone.md).
- Data-handling implementation spec → [docs/data-handling.md](docs/data-handling.md).
- DECISIONS.md — 13 locked decisions total.

**Phase 2 — Code (M1, M2, M3, M4, M5 — all done)**

- Module layout: `src/mcp_jupyter_kernel/` with `server.py`, `cli.py`, `config.py`, `auth.py`, `install.py`, `jupyter/{client,standalone,session,nb,output}.py`, `tools/{notebooks,cells,execute_,kernel_,inspect_,plots,debug_}.py`, `helpers/{bootstrap,redact}.py`.
- **M4 done — standalone mode.** `StandaloneSession` spawns a python3 kernel via `jupyter_client.AsyncKernelManager`. Full lifecycle: start, execute cells / code, capture stream / display_data / execute_result / error from iopub, persist outputs back to the .ipynb on disk, interrupt, shutdown. 7 integration tests against a real kernel pass.
- **M3 done — kernel introspection.** Kernel-side helper bootstrap (`__mjk`) injected via silent execute. `kernel.list_variables` and `inspect(target, mode)` tools wired through. `inspect` modes: auto (shape/dtypes/head), summary (describe/value_counts/stats), value (raw repr capped at 50 KB). 8 introspection tests pass on real DataFrames, ndarrays, dicts, strings.
- **M4 done — plots + debug tools.** `plots.capture_last` returns last matplotlib/plotly/altair PNG via session ring buffer. `debug.last_traceback` returns last captured iopub error. Verified end-to-end with a matplotlib render → base64 PNG → tool return.
- **M1 + M2 done — server mode.** `ServerSession` talks REST (httpx) + WS (websockets) to a running jupyter_server. Implements: `list_notebooks` (`GET /api/sessions`), `read_cells` (`GET /api/contents/{path}`), `insert_cell` (RTC-safe GET → check → PUT with `last_modified` conflict detection), `execute_cell` / `execute_code` (WS `execute_request` → iopub pump → `execute_reply`), `cancel` (`POST /api/kernels/{id}/interrupt`). 8 respx-mocked REST tests + 2 WS-mocked execute tests (scripted FakeWebSocket replays canonical iopub+shell sequences for success and error paths); live integration tests in `test_server_integration.py` exercise the WS path and run in CI.
- **M5 done — MCP wrapping + install.** `mcp-jupyter-kernel mcp install --client {claude-desktop|cursor|cline|all|claude-code}` writes the client's `mcpServers` entry atomically (tempfile → rename), preserves existing entries and non-MCP keys, refuses to overwrite invalid JSON. `mcp show` reports the config path. FastMCP build smoke test confirms all 10 tools register without import-cycle or signature mismatches.
- Tests: [tests/](tests/) — 33 passing locally; integration_server skipped until `JUPYTER_TEST_URL` set.
- CI: [.github/workflows/ci.yml](.github/workflows/ci.yml) — lint + smoke + integration_standalone + integration_server (Docker sidecar).
- Examples: [examples/01](examples/01-attach-to-jupyterlab.md), [02](examples/02-standalone-mode.md), [03](examples/03-data-exploration.md).

## Notable mid-session decisions

- **Wire-layer library swap.** `jupyter-kernel-client` (originally chosen) turns out to be sync; building directly on `httpx + websockets` gave us full async, ~300 lines, and easier `respx` unit testing. Recorded in DECISIONS 2026-05-13 (supersedes the original entry).
- **Name-mangling bug in kernel helpers** (caught + fixed). Python mangles `__name` inside class bodies to `_ClassName__name`. The kernel helper was using `__mjk_sys` inside `_MjkHelpers`, which became `_MjkHelpers__mjk_sys` — undefined → swallowed NameError → silent helper failures. Renamed module-level aliases to single-underscore (`_mjk_sys`, `_mjk_ns`); kept `__mjk` / `__mjk_json` only outside class scope.
- **IPython user_ns vs `__main__.__dict__`** (caught + fixed). User assignments live in `get_ipython().user_ns`, NOT `sys.modules['__main__'].__dict__` (that's the InteractiveShell's own dict). Helper now uses `get_ipython().user_ns` with `__main__` fallback for non-IPython kernels.
- **`silent=True` suppresses iopub stream output** (per messaging spec). Helper calls now use `silent=False, store_history=False` so `print(json.dumps(...))` round-trips through iopub.

**Phase 3 — Polish (~95% done)**

- [docs/install.md](docs/install.md) — quickstart + per-client install + troubleshooting.
- [docs/audit.md](docs/audit.md) — audit log schema + review patterns + rotation.
- [docs/launch.md](docs/launch.md) — pre-launch tweet sequence, blog post outline, Show HN body, r/* posts, runbook, sustain plan.
- [CONTRIBUTING.md](CONTRIBUTING.md) — quick-start, what we welcome, what we don't, testing rules.
- [docs/good-first-issues.md](docs/good-first-issues.md) — 8 starter tasks: bokeh plot capture, JupyterHub /user/X prefix validation, Cursor config verification, polars introspection, binary v1 WS subprotocol, R-kernel support, `health --from-mcp-client`, sklearn estimator summaries.
- `mcp-jupyter-kernel health` CLI — pings the configured Jupyter server, lists kernelspecs + open sessions. Setup-debugging command.
- README polished: real install commands, tool-surface preview, install.md link.
- **Live-test fixture: auto-spawning `jupyter_server` subprocess.** Activated by `MCP_JUPYTER_AUTOSPAWN_SERVER=1` (or external `JUPYTER_TEST_URL`). Closes the "wire layer never run against a real server" gap. **Caught a bug in the process** — `?type=notebook&format=json` query params on GET /api/contents return 400 from modern jupyter_server; the recon doc was wrong. Stripped to `?content=1` only. Both live integration tests pass.

## In flight

Only the hero GIF remains in Phase 3. Cannot be generated autonomously.

## Blocked / open questions

- Hero GIF — actual screen recording of the killer demo end-to-end. Needs a real Lab + Claude Desktop session.
- PyPI publish — needs maintainer credentials.

## Next-session checklist

1. Record the hero GIF. Replace the placeholder in README.
2. Live-run the killer demo: install into Claude Desktop, open the sample notebook in Lab, ask Claude to inspect `customer_df`. Smoke check.
3. PyPI publish.
4. Then execute the launch runbook in [docs/launch.md](docs/launch.md).

## Hours spent

| Phase | Budget | Spent | Remaining |
| --- | --- | --- | --- |
| 0 — Think | 6 | ~5 | ~1 |
| 1 — Design | 10 | ~6 | ~4 |
| 2 — Code | 55 | ~48 (M1–M5 + live fixture) | ~7 |
| 3 — Polish | 12 | ~10 (docs + CONTRIBUTING + GFIs + health CLI) | ~2 |
| 4 — Launch | 7 | ~2 (launch.md drafts) | ~5 |
| **Total** | **90** | **~71** | **~19** |
