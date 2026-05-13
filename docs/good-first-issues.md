# Good first issues

> Eight starter tasks. Pick one, comment on the issue, ship it. Each has a clear "definition of done" and pointers to the relevant code.

## 1. `plots.capture_last`: capture bokeh + holoviews PNGs

**Why:** Today, [src/mcp_jupyter_kernel/jupyter/output.py:_capture_plot_from](src/mcp_jupyter_kernel/jupyter/output.py) recognizes matplotlib, plotly, and altair. Bokeh and holoviews are common in scientific Python and produce display_data with `image/png` but also `application/vnd.bokehjs_exec.v0+json` etc.

**Done when:**
- A new `'source': 'bokeh'` branch in `_capture_plot_from`.
- Test in [tests/test_introspection.py](tests/test_introspection.py): render a bokeh figure, call `session.get_last_plot()`, assert source is `bokeh` and the PNG is non-empty.
- Skip the test if `bokeh` not installed.

**Estimated effort:** 1–2 hours.

---

## 2. JupyterHub: handle `/user/<name>` URL prefix at attach time

**Why:** [docs/auth.md](docs/auth.md) describes the config knob, but the live attach has not been tested against a real Hub. There's a good chance one of: WS URL construction, contents path encoding, or session listing breaks under the prefix.

**Done when:**
- An integration_server test that uses `base_url_prefix='/user/test'` and verifies `list_notebooks` + `read_cells` succeed.
- If a fix is needed, it lands in [src/mcp_jupyter_kernel/jupyter/client.py](src/mcp_jupyter_kernel/jupyter/client.py).

**Estimated effort:** 2–4 hours, including standing up a Hub locally.

---

## 3. Cursor's `~/.cursor/mcp.json` shape: verify the install writes a config Cursor actually reads

**Why:** Our [src/mcp_jupyter_kernel/install.py](src/mcp_jupyter_kernel/install.py) writes `{"mcpServers": {...}}` for Cursor. Cursor's docs say this is right, but we haven't verified live. Worth a manual integration test + a doc-comment about the verified path.

**Done when:**
- A documented "I tested this on Cursor version X" line in `docs/install.md`.
- If the format is different, fix `install.py` and add a regression test.

**Estimated effort:** 1 hour.

---

## 4. `inspect_summary` for `polars` DataFrames

**Why:** Polars usage has grown. Today our [src/mcp_jupyter_kernel/helpers/bootstrap.py](src/mcp_jupyter_kernel/helpers/bootstrap.py) handles pandas and numpy. Polars has its own `.describe()` and `.dtypes` that we should expose with the same MIME-bundle shape.

**Done when:**
- New branch in `_summarize_auto` and `inspect_summary` for `polars.DataFrame` and `polars.Series`.
- Tests under `integration_standalone` that skip if polars isn't installed.

**Estimated effort:** 2 hours.

---

## 5. Binary v1 WebSocket subprotocol negotiation

**Why:** Server-mode WS currently uses JSON framing (~33% larger for plot-heavy paths). The binary `v1.kernel.websocket.jupyter.org` subprotocol is documented and supported by modern `jupyter_server`. [src/mcp_jupyter_kernel/jupyter/client.py](src/mcp_jupyter_kernel/jupyter/client.py) module docstring calls this out as a TODO.

**Done when:**
- `_ensure_ws` requests the binary subprotocol; falls back to JSON on negotiation failure.
- A WS-mocked test that asserts the offset-table parsing roundtrips correctly.
- Live integration_server test that flips between the two by config.

**Estimated effort:** 4–6 hours. The binary framing is fiddly — see the recon doc.

---

## 6. R-kernel introspection

**Why:** Today our helper bootstrap assumes Python (`get_ipython().user_ns`, etc.). For R kernels (e.g., `ir`), `kernel.list_variables` and `inspect` fall back to a useless repr.

**Done when:**
- Detect kernel language at session start (via `/api/kernelspecs`).
- For R, inject a tiny R-side helper that emits the same JSON shape for `list_variables` / `inspect_auto` / `inspect_summary` / `inspect_value`.
- Integration test that spawns an `ir` kernel and exercises both tools.

**Estimated effort:** 6–8 hours. This is "first-class non-Python support" so propose the design in an issue first.

---

## 7. `health` command: add `--from-mcp-client` mode

**Why:** Today `mcp-jupyter-kernel health` reads its own config. But the user's friction point is "my Claude Desktop install isn't working" — they want to know if the JSON they wrote in `~/.../claude_desktop_config.json` is correct. We could re-read that config, parse our entry, and ping with those exact flags.

**Done when:**
- `mcp-jupyter-kernel health --from-mcp-client claude-desktop` reads the client's config, finds our `mcpServers[mcp-jupyter-kernel]` entry, and pings with its flags.
- Test using a tmp-path config.

**Estimated effort:** 2 hours.

---

## 8. `inspect`: improve the `auto` mode for sklearn estimators

**Why:** "What's in this trained model" is a common ask. For a fitted sklearn estimator, returning `{kind: 'sklearn_estimator', class: 'RandomForestClassifier', is_fitted: True, n_features_in_: 20, classes_: [0, 1], feature_importances_: [...]}` is far more useful than the default `{kind: 'other', repr: ...}`.

**Done when:**
- Branch in `_summarize_auto` (in [bootstrap.py](../src/mcp_jupyter_kernel/helpers/bootstrap.py)) for `sklearn.base.BaseEstimator`.
- Returns is_fitted (via `sklearn.utils.validation.check_is_fitted`), the model's fitted attrs (capped at the first ~10 by importance).
- Test that fits a RandomForestClassifier and asserts `kind == 'sklearn_estimator'`.

**Estimated effort:** 3 hours.

---

## How to claim one

Open or comment on the matching GitHub issue. We confirm assignment within 24 hours. If you go 7 days without commits or comments, the issue is re-opened to others.
