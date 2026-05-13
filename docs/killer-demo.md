# Killer demo — locked spec

> This is the scenario every tool in v1 must serve. If a proposed tool doesn't make this demo better, defer it. From master prompt §3.4.

## Scenario

A researcher has a Jupyter notebook open in Jupyter Lab. They're exploring a customer dataset. In Cursor (or Claude Code), they ask:

> "Look at my open notebook. What's in the `customer_df` dataframe? Suggest 3 plots that might be useful."

## Agent tool sequence

| # | Tool call | What it does |
| - | --------- | ------------ |
| 1 | `notebooks.list_open()` | Finds `customer_analysis.ipynb` (the one Lab has open). |
| 2 | `cells.read_recent(n=5)` | Sees the `load_csv` cell + a few exploration cells already executed. |
| 3 | `data.inspect(var="customer_df")` | Returns shape, dtypes, head(5). No raw rows beyond head. |
| 4 | `data.summary(var="customer_df")` | Returns `.describe()` for numerics, top-k `.value_counts()` for categoricals. |
| 5 | _(Claude reasons, suggests 3 plots)_ | No tool call. |
| 6 | _(optional)_ `cells.insert(after=10, code=<plot code>)` + `execute.cell(11)` | Plots get rendered in the live kernel. |
| 7 | `plots.capture_last()` | Returns the rendered PNG as base64. Claude looks at it and comments. |

## Acceptance criteria

- Wall time from prompt to final agent response: **< 30 s**.
- The user's notebook in Lab updates in real time as the agent works (no stale views).
- Plots appear inline in the notebook AND come back through MCP for the agent to see.
- No raw data beyond `head(5)` leaves the kernel unless the user explicitly asks for it.

## What this demo proves

- `notebooks.list_open` → agents can find the right notebook automatically; no manual path-typing.
- `cells.read_recent` → the agent has context about what the user has been doing.
- `data.inspect` + `data.summary` → the agent can reason about a dataframe without a single raw row crossing the LLM boundary (privacy story).
- `cells.insert` + `execute.cell` → the agent can write back into the notebook; the user keeps the artifact after the conversation ends.
- `plots.capture_last` → multimodal: the agent literally sees what it rendered. This is the wow moment in the demo GIF.

## Sample notebook for the demo

`tests/fixtures/sample_notebook.ipynb` should contain (target state after M1):

1. Markdown title cell.
2. `import pandas as pd; import numpy as np`
3. `customer_df = pd.read_csv("synthetic_customers.csv")` — loads a synthetic dataset (10k rows, ~6 columns: `id`, `age`, `tenure_months`, `mrr`, `country`, `churned`).
4. A couple of exploratory cells: `customer_df.head()`, `customer_df.dtypes`.

Synthetic dataset is generated in a separate fixture script. No real PII.
