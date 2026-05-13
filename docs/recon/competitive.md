# Competitive recon — Jupyter MCP servers

> Snapshot taken 2026-05-13. This is point-in-time and will go stale fast — re-run weekly per the master prompt §0.

## Top tier — production-adjacent

### 1. `datalayer/jupyter-mcp-server` — the clear leader

- **URL:** https://github.com/datalayer/jupyter-mcp-server
- **Stars / activity:** ~1.1k stars; last commit **2026-04-27** (v1.0.2); ~16 commits in the prior 30 days; 17 releases.
- **Tools (~17):** `list_files`, `list_kernels`, `connect_to_jupyter`, `use_notebook`, `list_notebooks`, `restart_notebook`, `unuse_notebook`, `read_notebook`, `read_cell`, `insert_cell`, `delete_cell`, `move_cell`, `overwrite_cell_source`, `edit_cell_source`, `execute_cell`, `insert_execute_code_cell`, `execute_code`, plus dynamic JupyterLab command tools via `jupyter-mcp-tools`.
- **Transport:** stdio + Streamable HTTP.
- **Mode:** **Attaches** to a running Jupyter server (requires `JUPYTER_URL`). **No standalone / spawn-kernel mode.**
- **Production signals:** test suite, GitHub Actions CI, frequent releases, dedicated docs site (`jupyter-mcp-server.datalayer.tech`), published Docker images, configs documented for VS Code / Cursor / Claude / Cline / Windsurf, multimodal output (images, plots) explicit.
- **Gaps mcp-jupyter can target:**
  - No first-class variable / dataframe / plot inspection tools — multimodal output is opportunistic, not proactive.
  - Requires Datalayer-flavored setup (`jupyter-collaboration` extension on the Jupyter side).
  - No headless / ephemeral mode.
  - 32 open issues at time of snapshot.

### 2. `block/mcp-jupyter` (Block, Inc. — Goose team)

- **URL:** https://github.com/block/mcp-jupyter — on PyPI as `mcp-jupyter` (this name is **taken**; we'll have to choose another package name).
- **Stars / activity:** ~42 stars; last release v2.0.2, **2025-09-30** — stale 7+ months.
- **Tools:** 4 consolidated (`query_notebook`, `modify_notebook_cells`, `execute_notebook_code`, `setup_notebook`).
- **Transport:** stdio + HTTP.
- **Mode:** Attach; requires `jupyter-collaboration` + `ipykernel`; preserves kernel variable state.
- **Production signals:** Apache-2.0, parametrized pytest LLM-eval framework, 10 releases.
- **Gaps:** stale; no dataframe/plot inspection tools; tool surface is too coarse for agents to discover capabilities.

### 3. `jbeno/cursor-notebook-mcp`

- **URL:** https://github.com/jbeno/cursor-notebook-mcp
- **Stars / activity:** 157 stars; latest release v0.3.1, **2025-07-16** (~10 months stale).
- **Tools:** 26 — full CRUD on cells, metadata, outputs, export, search, outline.
- **Transport:** stdio + Streamable-HTTP + SSE.
- **Mode:** **File-manipulation only.** Operates on `.ipynb` via `nbformat`. **Cannot execute cells.** No kernel at all.
- **Gaps:** the biggest functional gap among the leaders — no execution, no kernel state.

## Second tier

| Repo | Stars | Last activity | Notes |
| --- | --- | --- | --- |
| `ihrpr/mcp-server-jupyter` | 31 | 2025-02 (stale) | 6 tools, stdio, attach-only. |
| `jjsantos01/jupyter-notebook-mcp` | 130 | no releases | WS bridge into Jupyter 6.x; unpackaged. |
| `itisaevalex/jupyter-mcp-extended` | 11 | unknown | Fork of Datalayer with 15+ tools incl. **kernel variable inspection** + package install. Tiny audience, no releases. |
| `mstampfer/claude-code-notebook-mcp` | 6 | 4 commits | Node.js, file-only, no execution. |
| `UsamaK98/python-notebook-mcp` | low | — | Lightweight `.ipynb` editor. |
| `tofunori/mcp-jupyter-complete` | low | — | Position-based manipulation. |
| `shwetalsoni/jupyter-notebook-mcp-server` | low | — | FastMCP-based. |
| `ChengJiale150/jupyter-mcp-server` | low | — | Datalayer-style fork. |
| `azharlabs/mcp-jupyter-server` | low | — | Minor. |

## Official orgs

- **`modelcontextprotocol/servers`:** no Jupyter reference server. Reference servers are Everything, Fetch, Filesystem, Git, Memory, Time only.
- **`anthropics` GitHub org:** no Jupyter MCP server. Claude Code has native `.ipynb` read/edit built into the CLI (not via MCP). Anthropic blog has no Jupyter MCP post.
- **`jupyter` GitHub org:** no MCP server. `jupyter-ai-contrib/jupyter-server-mcp` (15 stars, v0.2.1 Apr 2026) is a generic extension that lets users register arbitrary Python functions as MCP tools — infrastructure, not a notebook agent server. **This is interesting**: we could conceivably build mcp-jupyter as a `jupyter-server-mcp`-registered tool bundle, not a standalone server. Worth a design spike in Phase 1.
- **Jupyter Discourse:** `complyue/jupyterlab-rtc-mcp` proposed Aug 2025 as a possible Jupyter subproject; seeking advocate, not on npm/PyPI.
- **VS Code:** ships a built-in Jupyter MCP server for its native notebooks (GA Jul 2025 with VS Code 1.102). Datalayer is the documented external option.
- **Cursor:** since v1.0, the agent can create/edit notebook cells (Sonnet-only) but **cannot run them** — the community gap Datalayer fills.

## Verdict

The "no production-quality Jupyter MCP server exists" thesis from the master prompt is **no longer fully valid as of 2026-05**. Datalayer's `jupyter-mcp-server` has crossed the threshold (1.1k stars, weekly commits, CI, docs site, Docker, multi-client configs).

Real gaps that mcp-jupyter can credibly target:

1. **First-class kernel introspection.** No leader exposes dedicated tools for `inspect_variable`, `dataframe_head`, `dataframe_schema`, `plot_as_image`, `traceback_explain`. Datalayer surfaces outputs but doesn't proactively summarize kernel state — exactly what agents need to reason efficiently.
2. **Standalone / spawn-kernel mode.** Every serious competitor *attaches* to a pre-running Jupyter Lab with `jupyter-collaboration`. For CI, sandboxes, ephemeral Claude Code sessions, and Codex-style runners, a zero-setup "spawn a kernel and go" mode is unfilled.
3. **Debugger-grade tools.** None expose `set_breakpoint`, `step`, post-mortem locals — true debugging beyond re-running cells.
4. **Lean tool surface tuned for Sonnet/Opus tool-calling.** Datalayer's 17+ tools is bloaty; Block's 4-tool consolidation is too coarse. 8–10 well-typed tools with strong schemas is the underserved sweet spot.

**Differentiate on: kernel-aware inspection + standalone mode + debugger semantics + lean surface.** Do NOT compete on cell CRUD — Datalayer has that.

## Implications for project plan

- **Reframe positioning:** "the kernel-aware Jupyter MCP" or "the headless Jupyter MCP," not "the only Jupyter MCP."
- **PyPI name:** `mcp-jupyter` is taken by Block. Need a new package name. Candidates: `jupyter-mcp-kernel`, `mcp-jupyter-kernel`, `jupiter-mcp` (cute but maybe too cute), `nbinspect-mcp`, `kerneltalk`. Defer to Phase 1.
- **Tool surface (master prompt §4.1) needs trimming.** The pre-recon design listed 22 tools, half of which overlap with Datalayer. Cut `notebooks.*`, `cells.*` to the minimum needed for the killer demo; double down on `data.*`, `kernel.*`, `plots.*`, `debug.*`.
- **The 1500-star 90-day target stays plausible** but only if we lead with the differentiation, not "yet another Jupyter MCP." Datalayer hit 1.1k in roughly a year with weaker positioning, so the ceiling is there.
- **Outreach posture:** still friendly to the Jupyter community, but explicitly position as complementary to Datalayer (not a replacement). Could even contribute the inspection tools upstream to them as a fallback plan.

## Sources

- [datalayer/jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server)
- [Datalayer commits](https://github.com/datalayer/jupyter-mcp-server/commits/main)
- [Datalayer docs site](https://jupyter-mcp-server.datalayer.tech/)
- [block/mcp-jupyter on PyPI](https://pypi.org/project/mcp-jupyter/)
- [jbeno/cursor-notebook-mcp](https://github.com/jbeno/cursor-notebook-mcp)
- [jjsantos01/jupyter-notebook-mcp](https://github.com/jjsantos01/jupyter-notebook-mcp)
- [ihrpr/mcp-server-jupyter](https://github.com/ihrpr/mcp-server-jupyter)
- [itisaevalex/jupyter-mcp-extended](https://github.com/itisaevalex/jupyter-mcp-extended)
- [mstampfer/claude-code-notebook-mcp](https://github.com/mstampfer/claude-code-notebook-mcp)
- [jupyter-ai-contrib/jupyter-server-mcp](https://github.com/jupyter-ai-contrib/jupyter-server-mcp)
- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- [Jupyter Discourse: jupyterlab-rtc-mcp proposal](https://discourse.jupyter.org/t/implemented-an-incoming-jupyterlab-mcp-server-finding-an-advocate-to-guide-it-into-a-subproject/37807)
- [VS Code MCP GA](https://github.blog/changelog/2025-07-14-model-context-protocol-mcp-support-in-vs-code-is-generally-available/)
- [Cursor 1.0 changelog](https://cursor.com/changelog/1-0)
