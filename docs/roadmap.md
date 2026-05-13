# Roadmap

Produced 2026-05-13 at end of Phase 2 audit-fix sweep. Living document — supersede with a new dated entry when scope changes.

## Versioning intent

Pre-1.0 semver: minor bumps may include behavior changes that tighten contracts (privacy, security); patch bumps are pure bug fixes.

| Version | Theme | Target window |
| --- | --- | --- |
| **0.1.0** | First PyPI publish — current code stabilized | this week |
| **0.2.0** | Privacy enforcement + stability | +2 weeks |
| **0.3.0** | Ecosystem fit (JupyterHub, performance, new tools) | +2 months |
| **0.4.0+** | Community-driven (R kernel, more libraries, ipywidgets) | as demanded |

Bump justifications [§(d)](#d-semver-bumps) below.

## (a) Deferred from Phase 2 audit

Items I flagged in Phase 1 but didn't fix in Phase 2 (architectural, > 50 LOC, API-breaking, or behavior-to-confirm).

| ID | Description | Proposed remediation | Effort |
| --- | --- | --- | --- |
| **C-4** | Redactor (`helpers/redact.py`) not applied to tool outputs | Wrap every tool's return at the FastMCP layer with a function that walks string fields, applies `redact()` and the `truncate` cap. Single decorator per tool; ~60–100 LOC + tests. | **M** |
| **C-5** | Audit log (`PrivacyConfig.audit_log`) loaded but no emission | Same wrap point as C-4: emit `{ts, tool, args, status, returned_bytes, wall_time_ms, redactions_applied, truncated}` JSONL line. Append-only file, never blocks on write failure. | **M** |
| **S-1** | `inspect` does `eval()` on agent-supplied `target` (behavior to confirm) | Write a DECISIONS entry explicitly accepting eval-on-target as the v1 trust model, OR restrict `mode='auto'` and `mode='summary'` to `^[A-Za-z_][\w.\[\]]*$` (identifier-or-attribute-chain). `mode='value'` still allows expressions. | **S** |
| **S-2** | Token in WS URL query string | Try `websockets.connect(..., extra_headers=[("Authorization", f"token {tok}")])`. If `jupyter_server` accepts header-only, drop the query-param fallback for HTTPS; keep for HTTP-test scenarios. | **S** |
| **Pf-1** | No WS reconnect / ping-pong | Wrap `_ensure_ws` with a watchdog: open with `ping_interval=20, ping_timeout=10`. On `ConnectionClosed`, evict from `self._ws` so the next call reconnects. Existing in-flight execute returns `status='timeout'`. ~60 LOC. | **M** |
| **Pf-2** | `_parse_helper_output` only reads last line of one stdout | Concatenate ALL stream/stdout texts into one buffer, then split on `\n` and try to JSON-parse from the back. ~10 LOC. | **S** |
| **Pf-3** | `insert_cell` does 3 round trips | Try `If-Unmodified-Since` header on PUT. If 412, refuse with `ConcurrentModificationError`. Replaces the recheck-GET. Needs feature test on `jupyter_server` to confirm support. | **S** |
| **T-3** | No FastMCP transport startup test | Pytest fixture spawns `mcp-jupyter-kernel standalone --transport http --port <free>`, polls `/`, asserts startup-within-N-seconds, then SIGTERMs. ~50 LOC. | **M** |
| **T-4** | No cancel-during-execute test | Start a `time.sleep(30)` cell as a task; call `cancel`; assert the task completes with `status='error'` and `ename='KeyboardInterrupt'`. | **S** |
| **T-6** | Plot capture only tested for matplotlib | Add plotly (kaleido) + altair (vega-lite) variants to `test_introspection`. Skip if libs absent. | **S** |
| **P2-batch** | C-6 (lock check), C-7 (`_join_source(None)`), C-8 (PNG type normalization), C-9 (kernel_status default), D-2 (last_modified refresh), Q-1 (callable type hint), Q-2 (`# type: ignore` on transport assignment), Q-3 (helper_call source build), Doc-4 (stale `data.value` doc), Doc-5 (STATUS phase claim) | Each is a 1–3 line fix with a one-test regression guard. Batch as one commit if convenient. | **S** (total) |

## (b) New feature proposals

### F1. Apply the redactor + audit log to tool outputs (delivers C-4 and C-5)

- **Motivation.** Privacy is mcp-jupyter-kernel's differentiator; docs claim redaction and audit emission. Neither is enforced today, so a determined data leak walks straight through.
- **User-visible behavior.** Each tool's text returns has obvious secrets (AWS keys, JWTs, `password=...`-shaped fragments) replaced with `<REDACTED:type>`. When `privacy.audit_log: <path>` is set, every tool call appends one JSON line to that file.
- **Acceptance criteria.** (1) Smoke test: `inspect` on a kernel variable holding `"my AWS_KEY=AKIA..."` returns redacted text. (2) Audit log enabled: 5 tool calls produce 5 JSONL lines with the schema in [docs/audit.md](audit.md). (3) Audit log path is unwritable: tool call still succeeds; one stderr line emitted. (4) Redactor pass adds < 50ms to a 1 KB return.
- **Effort.** M (~120 LOC + 6 tests).
- **Dependencies.** None. Wires into `tools/__init__.py:register_all`.

### F2. JupyterHub `/user/<name>/` prefix validation

- **Motivation.** Enterprise users are on Hub. Today's config has the knob but no integration test or end-to-end smoke check; high chance of a path / WS-URL construction bug under the prefix.
- **User-visible behavior.** `mcp-jupyter-kernel mcp install --client claude-desktop --jupyter-url https://hub.example.com --base-url-prefix /user/myname` works; all 10 tools function against Hub.
- **Acceptance criteria.** Live integration test under a JupyterHub-like prefix (mock or real Hub) exercises `list_notebooks`, `read_cells`, `execute_cell`, `inspect` end-to-end.
- **Effort.** M (test infra is the work; code changes likely 5–15 LOC for path construction edge cases).
- **Dependencies.** A Hub fixture (Docker-based or self-spawned `JupyterHub` via Python — possibly heavier than the current jupyter_server fixture).

### F3. Binary v1 WebSocket subprotocol

- **Motivation.** JSON framing is ~33% larger on plot-heavy paths. The binary `v1.kernel.websocket.jupyter.org` subprotocol is documented and supported by modern `jupyter_server`. Datalayer's leader uses it.
- **User-visible behavior.** No agent-visible change. Internal: WS handshake negotiates binary; fall back to JSON if rejected.
- **Acceptance criteria.** Unit test parses a binary frame using the offset-table; live integration test passes with binary subprotocol negotiated; benchmark shows ~30% reduction in bytes-on-wire for a 100 KB plot.
- **Effort.** M.
- **Dependencies.** None.

### F4. WS reconnect with ping-pong (delivers Pf-1)

- **Motivation.** Real Jupyter sessions outlive a single TCP connection (laptop sleep, network blip, server reload). Today a dropped WS = ServerSession is wedged.
- **User-visible behavior.** Tool call fails once with a clear "connection dropped, retrying" message; next call succeeds against a fresh WS.
- **Acceptance criteria.** Integration test forcibly closes the WS underneath ServerSession; next `execute_code` re-establishes and succeeds.
- **Effort.** M.
- **Dependencies.** None.

### F5. `cells.edit` and `cells.delete` (behind `--enable-destructive-edits` flag)

- **Motivation.** Most-asked v1.1 feature in [docs/good-first-issues.md](good-first-issues.md). Current "insert a corrected version below" pattern is awkward.
- **User-visible behavior.** Two new tools available when the flag is set. Default-off; an agent acting without explicit user consent can't destroy work.
- **Acceptance criteria.** Tools register only when flag is set; both tools persist via RTC-safe write path; standalone-mode + server-mode integration tests cover both.
- **Effort.** M.
- **Dependencies.** None.

### F6. `kernel.restart` tool

- **Motivation.** When a notebook's kernel state goes wrong (cached imports, stale globals), restart is the standard fix. Today the user must do it in Lab manually.
- **User-visible behavior.** Tool registered. Clears `__mjk` bootstrap state so the next tool call re-injects.
- **Acceptance criteria.** Tool restarts the kernel, `kernel.list_variables` post-restart returns the empty/builtin-only state.
- **Effort.** S.
- **Dependencies.** None.

### F7. Polars introspection in `inspect_auto` / `inspect_summary`

- **Motivation.** Polars usage growing fast in data science. Today `inspect` falls back to a plain repr for `pl.DataFrame`.
- **User-visible behavior.** `inspect("df", mode="auto")` on a polars DataFrame returns the same shape as pandas: `{kind: 'dataframe', shape, dtypes, columns, head, memory_usage_bytes}`.
- **Acceptance criteria.** Integration test skips if polars not installed; with it installed, exercises both modes.
- **Effort.** S.
- **Dependencies.** None (polars is an optional kernel-side dep we just sniff for).

### F8. sklearn estimator introspection

- **Motivation.** "What's in this trained model" is a common ask. Default `inspect_auto` falls back to repr which is useless for estimators.
- **User-visible behavior.** `inspect("model", mode="auto")` on a fitted estimator returns `{kind: 'sklearn_estimator', class, is_fitted, n_features_in_, classes_, feature_importances_ (top-K)}`.
- **Acceptance criteria.** Integration test fits a RandomForestClassifier, asserts the response shape.
- **Effort.** S.
- **Dependencies.** None.

### F9. R-kernel introspection

- **Motivation.** Many data scientists use R. Today our `__mjk` bootstrap assumes Python; non-Python kernels fall back to a degraded path.
- **User-visible behavior.** With an `ir` kernel, `kernel.list_variables` and `inspect` work the same as in Python. R-side helper injected at attach.
- **Acceptance criteria.** Live integration test against an R kernel exercises both tools.
- **Effort.** L (R-side helper code + cross-language kernel detection + R test infra).
- **Dependencies.** R + IRkernel installed for the test.

### F10. Bokeh / holoviews plot capture (delivers gfi-1)

- **Motivation.** Bokeh's iopub payload differs from matplotlib; today's `_capture_plot_from` misses it.
- **User-visible behavior.** `plots.capture_last` returns `source: 'bokeh'` (or `'holoviews'`) for renders from those libraries.
- **Acceptance criteria.** Integration test skips if bokeh absent; otherwise renders a bokeh figure and asserts the capture.
- **Effort.** S.

### F11. `health --from-mcp-client <name>` (delivers gfi-7)

- **Motivation.** User's actual question is "is my Claude Desktop config correct?" not "what does my config file say?" Today's `health` reads its own config.
- **User-visible behavior.** Reads the named client's `mcpServers["mcp-jupyter-kernel"]` entry, parses its args, runs the health check with those exact flags.
- **Acceptance criteria.** Tmp-path test creates a client config, runs `health --from-mcp-client cursor`, asserts the right URL + token-env are used.
- **Effort.** S.

### F12. Multi-notebook standalone mode

- **Motivation.** Standalone mode currently has a single notebook (`notebook_id == "local"`). For CI workflows that need to drive multiple notebooks in one server process, this is a blocker.
- **User-visible behavior.** `notebooks.list_open()` returns multiple entries; agent can address each independently.
- **Acceptance criteria.** New CLI: `mcp-jupyter-kernel standalone --notebook a.ipynb --notebook b.ipynb`. Both notebooks listable, each with its own kernel.
- **Effort.** M (touches StandaloneSession lifecycle; one kernel per notebook).
- **Dependencies.** None.

### F13. VS Code Jupyter integration validation

- **Motivation.** VS Code ships its own Jupyter MCP server. Either we complement it (their kernel + our introspection) or compete. Need a clear story.
- **User-visible behavior.** Documentation + integration test confirming our server can attach to a notebook open in VS Code's Jupyter.
- **Acceptance criteria.** Live walkthrough + smoke test.
- **Effort.** M.

## (c) Explicit non-goals for the next release

Decisions about what we are NOT doing — copied here from DECISIONS.md and the master prompt for visibility.

| Non-goal | Why |
| --- | --- |
| Compete with Datalayer's `jupyter-mcp-server` on cell CRUD | They own that surface; we differentiate on kernel introspection. |
| ipywidgets / interactive widget capture | Requires a `comm` protocol implementation. Architectural; defer until clear demand. |
| Colab / Kaggle / Databricks notebook execution | Their APIs are non-public / different. Possible v0.5+. |
| Auto-run-the-whole-notebook | Side-effect blast radius too large. Cell-by-cell with timeouts only. |
| Real-time collaborative editing | Out of scope — Jupyter Lab + RTC owns that. |
| Building our own notebook format | Stick to `.ipynb`. |
| Bundling Jupyter itself | Users bring their own. |
| Hero GIF generation by us | Manual screen recording, not in the autonomous lane. |
| Cross-kernel transactions | Each kernel session is independent. |
| Replacing JupyterLab UI | Complementary; never positioned as a UI. |

## (d) Semver bumps

| From → to | Triggering changes | Justification |
| --- | --- | --- |
| **0.0.1 → 0.1.0** | First public release. No removals from current code. PyPI publish; hero GIF; README polish. | Minor bump per pre-1.0 convention: substantial feature surface (10 tools, two modes, 58 tests, live integration validated) crosses from "internal" to "shipped." |
| **0.1.0 → 0.2.0** | Privacy enforcement (F1: redactor + audit log) + WS reconnect (F4) + S-1 eval policy decision + S-2 header-only WS auth + Pf-2 multi-stream JSON fix + the P2-batch cleanups. | Minor bump: behavior tightens (redactor applies — strict mode, not loose) but no public API removal. |
| **0.2.0 → 0.3.0** | New tools (F5, F6), introspection coverage (F7, F8, F10), JupyterHub validation (F2), binary v1 WS (F3). | Minor bump: additive tools + perf + ecosystem polish. No breaks. |
| **0.3.0 → 0.4.0** | F9 R-kernel support, F12 multi-notebook standalone, F13 VS Code integration validation. | Minor bump: significant new modes. Multi-notebook standalone changes `notebook_id` semantics in standalone mode (was always `"local"`, now may be others) — flag this as a (minor pre-1.0) compat break with a migration note. |
| **1.0.0** | All v1 deferred items addressed, public API frozen. | Major bump: from "moving target" to "API stability promise." Target after one full v0.4 → v0.5 cycle, when the surface has been beaten on by real users. |

## (e) Priority ordering

Not a flat list — grouped by tier, each item with a one-line rationale.

### Tier 0 — must ship with v0.1.0 (the first publish, this week)

1. **PyPI publish.** Operational; unblocks every subsequent line item.
2. **Hero GIF.** Demos sell the wedge; nothing else does.
3. **README copy review.** First-impression artifact.

### Tier 1 — must ship with v0.2.0 (privacy/stability — the trust layer)

4. **F1 Redactor + audit log wiring (C-4 + C-5).** Privacy promises in docs that the code currently doesn't keep. The strongest single piece of marketing surface this project has.
5. **F4 WS reconnect (Pf-1).** Real-world server-mode sessions outlive a TCP connection. Without it, every "my agent stopped working" issue is going to point here.
6. **S-1 `inspect` eval policy decision.** Codifies the trust model. Either accept eval-on-target or restrict `auto`/`summary` to identifier-paths. Either is fine; deciding-and-documenting is the action.
7. **S-2 header-only WS auth.** Eliminates the "token in URL" log leak risk if `jupyter_server` cooperates.
8. **Pf-2 multi-stream JSON reassembly.** Cheap defense against a real bug class for large summaries — 10 LOC.
9. **P2-batch cleanup.** Combined ~15 minutes of effort; clears the lint/quality backlog before it grows.

### Tier 2 — high-value for v0.3.0 (ecosystem fit)

10. **F2 JupyterHub validation.** Largest unaddressed user segment; without it, enterprise asks have to be deflected.
11. **F3 Binary v1 WS subprotocol.** Standard table-stakes for plot-heavy use; Datalayer has it.
12. **F11 `health --from-mcp-client`.** Lowers the support burden — users self-debug.
13. **F5 cells.edit + cells.delete (gated).** Most-asked v1.1 feature; gated so default install is safe.
14. **F6 kernel.restart.** Common; trivial to add once the gating pattern from F5 is in place.

### Tier 3 — feature polish for v0.3.x / v0.4

15. **F7 polars introspection.** Small additive win; growing user base.
16. **F8 sklearn estimator introspection.** Common ask; small additive win.
17. **F10 bokeh / holoviews plot capture.** Round out the plot-library coverage.
18. **T-3 + T-4 + T-6 test additions.** Coverage gaps we can backfill once nothing more urgent is open.

### Tier 4 — community-demand-only

19. **F9 R-kernel introspection.** Big differentiation but only if users actually ask. Don't build speculatively.
20. **F12 Multi-notebook standalone.** Same — wait for the CI workflow user to surface the need.
21. **F13 VS Code Jupyter integration validation.** Same.
22. **Pf-3 `insert_cell` round-trip reduction.** Real-world latency hasn't been measured; YAGNI until it has.

### Out (don't pull from here without re-justifying)

- ipywidgets / `comm` protocol — too much surface for unclear gain.
- Colab / Kaggle integration — non-public APIs, maintenance burden.
- Auto-run-the-whole-notebook — anti-pattern by master-prompt definition.
- Cross-kernel transactions — architectural mismatch with our session abstraction.
