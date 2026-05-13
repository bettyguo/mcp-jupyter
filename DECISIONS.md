# DECISIONS

> Append-only log of locked decisions. New rows go at the bottom. When a decision is overturned, add a new row that supersedes the old one (don't edit history). Keep entries short — link out to design docs for detail.

## Format

```
### YYYY-MM-DD — <short title>

**Decision:** <one sentence>
**Why:** <one or two sentences, the load-bearing reason>
**Alternatives rejected:** <bullets>
**Supersedes:** <none | YYYY-MM-DD title>
**Link:** <design doc or master-prompt section>
```

---

### 2026-05-13 — Language: Python 3.11+

**Decision:** Python 3.11 minimum, no other language considered.
**Why:** Jupyter is Python-native; the canonical client libraries (`nbformat`, `jupyter_client`, `jupyter_server`) all live in Python. Anything else adds an FFI layer to the most important integration surface in the project.
**Alternatives rejected:** TypeScript (would need to reimplement Jupyter wire protocol); Rust (same reason, plus smaller MCP/Jupyter library surface).
**Link:** Master prompt §1.

---

### 2026-05-13 — MCP framework: fastmcp

**Decision:** `fastmcp` for the MCP server. Transports: stdio + Streamable HTTP.
**Why:** It's the canonical Python MCP framework with both transports. Matches the model Claude Desktop / Cursor / Codex expect.
**Alternatives rejected:** Raw `mcp` SDK (more boilerplate); writing our own (no reason).
**Link:** Master prompt §1.

---

### 2026-05-13 — Jupyter integration via REST/WS, not direct kernel poking

**Decision:** Server mode is the default. We talk to a running `jupyter_server` over its REST + WebSocket API. We do NOT reach around the server to poke kernels directly when a server is present.
**Why:** When the user has a notebook open in Lab, Lab maintains canonical state (dirty buffers, RTC sessions, sidecar widgets). Bypassing it causes drift between what the user sees and what we see. The Jupyter team supports the REST API as the integration surface.
**Alternatives rejected:** Always-attach via `jupyter_client` (causes drift + breaks Lab); ZMQ kernel sniffing (fragile, undocumented).
**Link:** Master prompt §1, anti-pattern #1.

---

### 2026-05-13 — Standalone mode is a first-class feature, not an afterthought

**Decision:** Ship a `mcp-jupyter standalone <notebook.ipynb>` mode that spawns a kernel via `jupyter_client` with no server in the loop. All tools work identically.
**Why:** Half the value for headless / CI / "I just want an agent to run my notebook" users. Without it, mcp-jupyter is only useful when Lab is already open — which excludes a big use case.
**Alternatives rejected:** Server-mode-only (loses headless use); spawn an ephemeral `jupyter_server` (more weight, no upside).
**Link:** Master prompt §4.3.

---

### 2026-05-13 — Default to summaries, not raw data

**Decision:** Inspection tools return structured summaries (shape, dtypes, head, describe). The only raw-data path is `data.value(expression)`, which is documented as opt-in and warns the LLM in its tool description.
**Why:** Researchers' notebooks frequently contain PII, embargoed research data, and customer data. A tool that streams whole dataframes to an LLM by default is a privacy footgun and will get the project blacklisted by careful users.
**Alternatives rejected:** "Just trust the user to know" (most agents call every tool eagerly; default behavior is what matters); per-call permission prompts (too much friction).
**Link:** Master prompt §3.3, §4.4; docs/privacy.md.

---

### 2026-05-13 — Cell-by-cell execution only; no auto-run-the-whole-notebook

**Decision:** v1 exposes `execute.cell(idx)` and `execute.code(snippet)` only. No `execute.run_all`.
**Why:** Auto-running a researcher's whole notebook can OOM the kernel, melt a GPU, charge their API credits, or trigger irreversible side effects (sending emails, writing to prod DBs). The blast radius is too large.
**Alternatives rejected:** `run_all_with_confirmation` (confirmation flows are awkward through MCP and agents tend to bulldoze them); `run_all_with_per_cell_timeout` (still loses the bigger blast-radius arg).
**Link:** Master prompt §1 non-goals, anti-pattern #3.

---

### 2026-05-13 — License: BSD-3-Clause

**Decision:** BSD-3-Clause.
**Why:** Matches Jupyter's own license; signals ecosystem alignment when we engage Jupyter steering / Discourse.
**Alternatives rejected:** MIT (fine but less aligned), Apache-2.0 (more legal weight than the project needs).
**Link:** Master prompt §1.

---

### 2026-05-13 — Positioning pivot: kernel introspection + standalone + debugger semantics

**Decision:** mcp-jupyter's differentiation is **kernel-aware inspection, standalone mode, debugger-grade tools, and a lean tool surface**. It is NOT "the only Jupyter MCP" and NOT "general cell CRUD." Datalayer's `jupyter-mcp-server` already owns the CRUD niche.
**Why:** Phase 0.1 recon found that `datalayer/jupyter-mcp-server` is production-quality as of 2026-05-13: ~1.1k stars, weekly commits, CI, docs site, Docker, multi-client configs. The master-prompt thesis "no production-quality Jupyter MCP server exists" is invalid. To hit the 1500-star 90-day target we need a clear differentiation story, not "yet another."
**Concrete consequences:**
- v1 leads with `data.inspect`, `data.summary`, `kernel.list_variables`, `plots.capture_last`, `debug.last_traceback` — not with cell CRUD.
- `cells.*` and `notebooks.*` stay in v1 but are minimal — only what the killer demo requires.
- Standalone mode is a launch-day feature, not deferred.
- Outreach explicitly positions mcp-jupyter as complementary to Datalayer.
**Alternatives rejected:** Compete head-on with Datalayer on tool count (loses on velocity); abandon the project (the introspection gap is real and unfilled).
**Link:** docs/recon/competitive.md, master prompt §10 "Tool count" question.

---

### 2026-05-13 — PyPI/package name TBD — `mcp-jupyter` is taken

**Decision:** The PyPI name `mcp-jupyter` is occupied by Block, Inc.'s server. Picking a new distribution name is deferred to early Phase 1 but must happen before any release. The repo dir and import path can stay `mcp_jupyter` internally for now; the *distribution* name is what blocks PyPI.
**Why:** PyPI name collisions are not recoverable post-launch. Need to commit to a name before the first GitHub README hits HN.
**Candidates to evaluate in Phase 1:** `jupyter-mcp-kernel`, `mcp-jupyter-kernel`, `mcp-nbkernel`, `nbinspect-mcp`, `kerneltalk`. The name should signal the kernel/inspection angle.
**Alternatives rejected:** Force a fork-of-block model (their package is stale but extant — confusing to users); use `mcp_jupyter2` (cheap-looking).
**Link:** docs/recon/competitive.md §2.

---

### 2026-05-13 — Build server-mode wire layer on `jupyter-kernel-client`, not from scratch

**Decision:** Server-mode (talking to a running Jupyter server) uses Datalayer's `jupyter-kernel-client` Python library as the REST + WebSocket transport. Standalone-mode uses `jupyter_client.AsyncKernelManager` directly.
**Why:** `jupyter-kernel-client` is actively maintained by the same team that ships the leading Jupyter MCP server. It already handles auth, the binary v1 WS subprotocol, message correlation, and reconnect. Reimplementing the messaging spec ourselves is 5–10 hr of work for no differentiation. Cost-of-dependency: a single Datalayer maintainer; mitigated by the fact that we can vendor or fork if it goes unmaintained.
**Alternatives rejected:** Raw `httpx` + `websockets` (more code, same outcome); fork Datalayer's MCP server (loses our positioning).
**Link:** docs/recon/jupyter-api.md §4.
**Superseded:** see 2026-05-13 "Server-mode wire layer on httpx + websockets" below.

---

### 2026-05-13 — Server-mode wire layer on httpx + websockets directly (supersedes the jupyter-kernel-client decision above)

**Decision:** Implement server-mode REST + WebSocket transport directly on `httpx` (async REST) and `websockets` (async WS). Do not depend on `jupyter-kernel-client`.
**Why:** While implementing M1+M2 I discovered `jupyter-kernel-client` exposes a synchronous API (`with KernelClient(...) as k: k.execute(...)`). Our `KernelSession` interface is async; wrapping a sync lib in a thread pool just to fit the abstraction is awkward, hurts observability, and creates lifecycle hazards (the lib's session lifecycle doesn't compose cleanly with our async with). Direct `httpx + websockets` is ~300 lines and gives us: full async, transparent message envelopes (easier to debug + unit-test with `respx`), no transitive Datalayer dependency, and full control over the binary v1 subprotocol negotiation when we add it.
**Cost:** ~200 extra lines vs the wrapper approach. Acceptable.
**Alternatives rejected:** Thread-pool wrapper around `jupyter-kernel-client` (awkward); fork-and-async `jupyter-kernel-client` (more drag than DIY).
**Link:** src/mcp_jupyter_kernel/jupyter/client.py module docstring.
**Supersedes:** 2026-05-13 "Build server-mode wire layer on jupyter-kernel-client".

---

### 2026-05-13 — Negotiate the binary v1 WS subprotocol when available

**Decision:** Server-mode WS clients request `Sec-WebSocket-Protocol: v1.kernel.websocket.jupyter.org`. Fall back to JSON frames if the server doesn't echo it.
**Why:** Plots (matplotlib PNG, plotly PNG via kaleido) and large dataframe heads ride the WS as base64 in JSON otherwise. Binary subprotocol cuts payload size ~33% and avoids the JSON encode/decode tax on hot paths.
**Alternatives rejected:** JSON-only (slower for the plots we promise in the killer demo).
**Link:** docs/recon/jupyter-api.md §2.

---

### 2026-05-13 — RTC-safe writes: read-then-write with last_modified check; refuse on conflict

**Decision:** All `cells.edit` / `cells.insert` / `cells.delete` operations in server mode: (1) GET the notebook, (2) record `last_modified`, (3) construct the new notebook in-memory via `nbformat`, (4) PUT only if a fresh GET confirms `last_modified` is unchanged. On conflict: refuse and surface a clear error to the agent ("notebook changed since read — re-read and retry").
**Why:** Lab + `jupyter_collaboration` keep edits in an in-memory Y-doc that periodically flushes to disk. A naive PUT through `/api/contents` can clobber the user's live edits or be silently overwritten. Read-then-write with conflict detection is the minimum bar. Going further (writing into the Y-doc via `/api/yjs/...`) is post-v1.
**Alternatives rejected:** Always-write through `/api/yjs` (Y-doc binary protocol is heavier than we can budget in v1); refuse to write whenever Lab is connected (too restrictive — kills the killer demo for the very users we want).
**Link:** docs/recon/jupyter-api.md §6, docs/privacy.md "Notebook-write safety."

---

### 2026-05-13 — Raise the iopub rate limit at server-attach time; warn in standalone mode N/A

**Decision:** In server mode, on first attach, mcp-jupyter checks the server's `iopub_data_rate_limit` config (best-effort — via `/api/status` or `/api/config` if exposed; otherwise documented). If the limit looks like the default 1 MB/s, log a warning to the agent's tool response that long output cells may silently truncate. We do NOT mutate the server config — that's the operator's call.
**Why:** Tight print loops or image bursts hit the limit and the server silently drops iopub. The agent sees missing output and has no signal why. Surfacing the limit in a tool response gives the agent a debug path. Standalone mode is unaffected (no server in the loop).
**Alternatives rejected:** Mutate the server config on attach (overstep — we're a guest in the user's Jupyter); ignore (footgun).
**Link:** docs/recon/jupyter-api.md §6.

---

### 2026-05-13 — Distribution name locked: `mcp-jupyter-kernel`

**Decision:** PyPI distribution name is `mcp-jupyter-kernel`. Import name is `mcp_jupyter_kernel`. CLI binary is `mcp-jupyter-kernel`. Source directory is `src/mcp_jupyter_kernel/`.
**Why:** Keeps the `mcp-jupyter` brand prefix (discoverable when users search "jupyter mcp"); `-kernel` suffix is explicit about the kernel-aware differentiator; avoids both PyPI collision with Block's `mcp-jupyter` AND import-namespace collision (since we changed the import name too, both packages can coexist in one venv if anyone ever wants that). Candidates rejected: `nbinspect-mcp` (loses Jupyter SEO), `kerneltalk` (cute, opaque), `mcp-nbkernel` (loses Jupyter SEO), `jupyter-mcp-kernel` (could be mistaken for an official Jupyter project, problematic in outreach).
**Link:** pyproject.toml, recon/competitive.md §2.

---

### 2026-05-13 — Packaging: standalone MCP server, not a `jupyter-server-mcp` extension

**Decision:** mcp-jupyter-kernel is a standalone MCP server binary. We do not package as a `jupyter-server-mcp` extension. Re-evaluate after v1 if there's user demand for it.
**Why:** Standalone mode (spawning a kernel without any Jupyter server) is half our differentiation — by definition it can't live inside a Jupyter server extension. Server mode could in principle be packaged as a `jupyter-server-mcp` extension, but `jupyter-ai-contrib/jupyter-server-mcp` has 15 stars and is unproven infrastructure; betting our packaging on it is risky. Easier to ship as a normal MCP server and add an adapter later if needed.
**Alternatives rejected:** Dual packaging (doubles surface area for marginal gain); extension-only (kills standalone mode entirely).
**Link:** DECISIONS pending question resolved.

---

### 2026-05-13 — Dev/CI environment: Docker sidecar for integration tests, local Jupyter for development

**Decision:** CI runs integration tests against a `jupyter/scipy-notebook` Docker sidecar with a known token. Local development assumes the contributor has `jupyter lab` installed (`pip install -e .[dev]` provides it).
**Why:** Reproducible, version-pinnable, matches master prompt §6.4. Local install for dev is `pip install jupyterlab` away and avoids contributors needing Docker just to iterate on the inspector tool.
**Link:** master prompt §6.4, M1 DoD.

---

### 2026-05-13 — v1 tool surface locked at 10 tools

**Decision:** Ten tools in v1: `notebooks.list_open`, `cells.read_recent`, `cells.insert`, `execute.cell`, `execute.code`, `execute.cancel`, `kernel.list_variables`, `inspect` (polymorphic with `mode` ∈ {`auto`, `summary`, `value`}), `plots.capture_last`, `debug.last_traceback`. Defer to v1.1: `notebooks.list_all`, `notebooks.open`, `cells.read_all`, `cells.edit`, `cells.delete`, `kernel.restart`, `kernel.status`, `plots.list_recent`.
**Why:** Within the master prompt's 20-tool ceiling. Every tool serves either the killer demo or the kernel-introspection differentiator. Polymorphic `inspect` collapses three would-be tools into one with a clear mode argument that doubles as the privacy posture (`auto`/`summary` safe, `value` carries an explicit warning). Defers `cells.edit`/`cells.delete` because an agent can prefix-insert a corrected cell — less destructive and aligns with our safety posture.
**Link:** docs/tools.md.

---

### 2026-05-13 — `inspect` is polymorphic; `mode` argument carries privacy posture

**Decision:** Single `inspect(target, mode='auto')` tool. `mode='auto'` returns type-aware summaries (shape/dtypes/head). `mode='summary'` returns describe()/value_counts() for tabular types. `mode='value'` returns the raw repr capped at 50 KB and the tool description carries an explicit "may contain sensitive data" warning.
**Why:** Three modes mean the agent's choice of mode is itself the consent signal — `mode='value'` is the agent saying "I have explicit user authorization to see this." Cleaner than separate tools because the LLM's training biases toward calling the cheapest tool first, and `auto` IS the cheapest.
**Link:** docs/tools.md tool #8, docs/data-handling.md.

---

## Pending decisions (do not resolve speculatively — wait for the milestone that forces the call)
- **JupyterHub multi-user support in v1?** Master prompt recommends yes. Defer concrete design to M1 auth work.
- **`data.value` LLM-visible warning wording.** Locked at "default to summaries"; exact wording to be drafted in M3 and reviewed before launch.
- **Auto-restart kernel on tool errors?** Master prompt recommends no. Confirm at M3 once we've seen real error modes.
- **Colab API support?** Recommended v2-only. Re-evaluate at week-4 sustain checkpoint based on community ask.
