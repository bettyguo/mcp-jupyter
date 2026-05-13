# Launch kit — drafts

> Pre-launch + launch-day assets. None of this has been sent yet. Pull, edit, and post when the time comes.

## Pre-launch sequence (T-14 → T-0)

### T-14 days — soft signal

Twitter / Mastodon / Bluesky:

> I've been wanting Claude to actually understand my Jupyter notebooks for months — not the JSON, the kernel state. So I'm building it. Open-source MCP server, ~2 weeks out. Reply if you want early access.

### T-7 days — the inspect demo

GIF: a researcher asks Claude "what's in `customer_df`?" The agent calls `inspect(target="customer_df")` and Claude responds with shape + dtypes + first 5 rows — without any raw rows leaking. Caption:

> Most "Jupyter MCP" servers see your .ipynb as JSON. mcp-jupyter-kernel sees what's actually in the kernel — and stays out of raw data by default. v0.1 next week.

### T-2 days — the full demo

GIF: the killer demo end to end. Open notebook in Lab → ask Claude for plot suggestions → Claude calls `inspect` + `inspect mode='summary'` → suggests 3 plots → inserts a cell → runs it → calls `plots.capture_last` → comments on the rendered plot. Show the plot rendering. Caption:

> 30 seconds, 7 tool calls, one rendered plot. mcp-jupyter-kernel — your agent sees the kernel, not just the .ipynb. Launch tomorrow.

### T-0 — launch day

See "Launch-day kit" below.

---

## Blog post (T-1)

**Title:** Why agents are bad at Jupyter — and what to do about it

**Outline (target 1500 words):**

1. The Jupyter agent problem in one paragraph. Cursor / Claude / Codex see `.ipynb` as text. They cannot answer "what's in `customer_df`?" without re-running cells. They cannot see plots. They cannot tell you why the last cell raised. The information they need is in a process they can't see.

2. The MCP angle. An MCP server can bridge agent ↔ live kernel. The basics — cell read / edit / execute — are well-served by Datalayer's `jupyter-mcp-server`. Credit them clearly.

3. What's still missing: kernel introspection.
   - Variables (names + types + sizes — never values by default).
   - DataFrame summaries: shape, dtypes, head(5), describe(), value_counts() for low-card categoricals.
   - Plot capture as base64 PNG.
   - Last-traceback access without re-running.

4. The privacy story. Researchers' data is sensitive — PII, embargoed research, customer data. Show how the three `inspect` modes (`auto` / `summary` / `value`) carry the privacy posture, and why default-safe matters more than convenience.

5. Two-mode operation. Server mode for "I have Lab open." Standalone mode for CI / sandbox / headless. Why both matter.

6. The technical pieces. `__mjk` kernel-side helper bootstrap. The `last_modified` RTC conflict trick. The shared `ExecutionState` collector between server + standalone modes.

7. Try it. `pip install mcp-jupyter-kernel && mcp-jupyter-kernel mcp install --client claude-desktop`. Star the repo.

---

## Launch-day kit

### Show HN post

**Title:** `Show HN: mcp-jupyter-kernel – Let your AI agent see what's actually in your kernel`

**Body:**

> Cursor / Claude Code / Codex read your `.ipynb` files as JSON. They cannot tell you what's in `customer_df`, can't see the plot you just rendered, and can't tell you why the last cell raised. mcp-jupyter-kernel closes that gap.
>
> It's an MCP server with two operating modes:
> - **Server mode**: attach to a running Jupyter Lab / Notebook 7 / JupyterHub.
> - **Standalone mode**: spawn a kernel directly. No Jupyter server. Useful for headless / CI / sandboxed runs.
>
> 10 tools. The differentiation is `inspect(target, mode)` — three modes:
> - `auto` (default): type-aware summary (shape, dtypes, head(5)).
> - `summary`: describe() + top-K value_counts() for low-cardinality categoricals.
> - `value`: raw repr (capped at 50 KB), with an explicit "may contain sensitive data" warning baked into the tool description.
>
> Datalayer's jupyter-mcp-server is the existing leader for cell CRUD. We're complementary, not a replacement — we focus on kernel introspection and standalone use.
>
> Install: `pip install mcp-jupyter-kernel && mcp-jupyter-kernel mcp install --client claude-desktop`.
>
> Code: https://github.com/<...>/mcp-jupyter-kernel
> Docs: https://github.com/<...>/mcp-jupyter-kernel/blob/main/docs/install.md
>
> Built in Python on `httpx + websockets` (for server mode) and `jupyter_client.AsyncKernelManager` (for standalone). BSD-3-Clause. Feedback welcome.

### r/MachineLearning [P] post

Same as HN but framed as "[P]" with research framing: "Useful for replication studies, exploratory data analysis with an agent, automated runs of analysis notebooks."

### r/Jupyter, r/DataScience

Practical framing — focus on the day-to-day workflow:

> If you've ever asked Cursor what's in a DataFrame in your notebook and gotten back the JSON of the cell instead of the actual contents, this is for you. mcp-jupyter-kernel exposes a `kernel.list_variables` and `inspect()` tool that gives the agent the real shape + head, without dumping raw rows to the LLM by default.

### r/MCP, r/ClaudeAI

Audience: people running MCP-aware agents. Focus: the 10-tool surface, the standalone mode, the privacy posture.

### Direct outreach (one-shot DMs)

- Jupyter core devs (be respectful — community-driven; lead with "complementary to Datalayer's server")
- Vicki Boykis
- Jeremy Howard
- Hamel Husain
- VS Code Jupyter team (their built-in MCP server can't introspect; we complement it)
- Datalayer team (heads-up + offer to upstream the inspect helpers if they want them)

### Posts NOT to make

- No comparison-table tweets that punch at Datalayer. We're complementary.
- No tweet that overclaims privacy ("your data never leaves the kernel"). The promise is "not by default."

---

## Launch-day runbook

| T | Action |
| --- | --- |
| -30m | Final pre-flight: docs hosted, README hero GIF working, install command tested fresh in a new venv. |
| 0 | Post Show HN. Tweet within 5 min with the same link. |
| +15m | Post to r/MCP + r/ClaudeAI. |
| +30m | Post to r/MachineLearning [P] and r/DataScience. |
| +1h | Send DMs to the 6 named influencers. Mention the HN link in passing — they'll either care or not. |
| +2h | Refresh issues + PRs. Respond to every comment within 30 min for the first 4 hr. |
| +4h | Pause and post a "thanks!" tweet. Don't double-down on aggressive promotion. |
| +24h | First metrics retro: stars, PyPI installs, top issues. |

**Timing**: avoid Mondays (HN noise) and Fridays (drop-off). Tuesday or Wednesday 7am Pacific is conventional but data scientists are evening / late-night people; Tue 4pm Pacific also works.

---

## Sustain plan

- **Week 1**: same-day response to every issue. PRs get a "thanks, will review" within 1 hr. Don't try to ship 5 features in week 1.
- **Week 2**: "First 50 users" blog post. Themes: what people actually do with it, the standalone-mode discovery moment, surprises.
- **Week 3**: Colab/Kaggle reconnaissance. Are people asking for it? If yes, scope a v1.1.
- **Week 4**: JupyterCon talk submission. The angle: "MCP for Jupyter — when, why, and the privacy story."
- **Week 8**: Re-evaluate the wedge. Has Datalayer added inspection tools? Has VS Code's built-in MCP grown a `inspect()` equivalent? Sharpen positioning if needed.
