# Tool surface — locked v1

> **10 tools.** Every tool justifies its slot against the killer demo or the kernel-introspection differentiator. Cell-CRUD coverage is intentionally minimal — Datalayer's `jupyter-mcp-server` owns that surface.

Locked 2026-05-13 in DECISIONS. Changes need a new DECISIONS entry.

## Design principles

- **One polymorphic `inspect` tool** instead of three (`data.inspect`, `data.summary`, `data.value`). Fewer tools, clearer agent intent. The `mode` argument is what carries the privacy posture.
- **Server-mode and standalone-mode share the same tool schemas.** The transport is swappable below the tool layer.
- **All return payloads cap at 50 KB.** Beyond that, `truncated: true` and a count of bytes dropped.
- **Every tool description leads with what it does, ends with when NOT to use it.** Negative guidance is what stops eager agents from over-calling.

## The 10 tools

### 1. `notebooks.list_open`

Find notebooks currently open in the connected Jupyter server (server mode) or report the single attached notebook (standalone mode).

```json
{
  "name": "notebooks.list_open",
  "description": "List notebooks currently open in the Jupyter session. Use this first to find the notebook_id you'll pass to other tools. In standalone mode returns a single entry for the attached notebook.",
  "inputSchema": { "type": "object", "properties": {}, "additionalProperties": false },
  "returns": "Array<{notebook_id: string, path: string, kernel_id: string, kernel_status: 'idle'|'busy'|'starting'|'dead', last_activity: string}>"
}
```

### 2. `cells.read_recent`

Read the last N cells of a notebook to grasp current context.

```json
{
  "name": "cells.read_recent",
  "description": "Read the most recent N cells of a notebook (default 5). Use this to ground in current context before reasoning about a notebook. For a single specific cell, pass n=1 from the cell's index (negative offsets are supported).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": { "type": "string" },
      "n": { "type": "integer", "minimum": 1, "maximum": 50, "default": 5 }
    },
    "required": ["notebook_id"],
    "additionalProperties": false
  },
  "returns": "Array<{index: int, cell_type: 'code'|'markdown'|'raw', source: string, outputs?: object[], execution_count?: int}>"
}
```

### 3. `cells.insert`

Insert a new cell after a given index. In server mode, this respects the RTC-safe write protocol (last_modified check; refuses on conflict).

```json
{
  "name": "cells.insert",
  "description": "Insert a new cell after the given index. Use to add agent-authored code that the user should keep. In server mode, refuses if the user has edited the notebook since you last read it — re-read with cells.read_recent and retry.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": { "type": "string" },
      "after_index": { "type": "integer", "minimum": -1 },
      "code": { "type": "string" },
      "cell_type": { "type": "string", "enum": ["code", "markdown"], "default": "code" }
    },
    "required": ["notebook_id", "after_index", "code"],
    "additionalProperties": false
  },
  "returns": "{new_index: int} | {error: 'conflict', last_modified: string}"
}
```

### 4. `execute.cell`

Execute a cell that already exists in the notebook.

```json
{
  "name": "execute.cell",
  "description": "Execute the cell at the given index against the notebook's kernel. Outputs are persisted in the notebook AND returned to you. Default timeout 60s; hard max 1800s. If you only need a quick check, use execute.code instead — it doesn't store anything.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": { "type": "string" },
      "cell_index": { "type": "integer", "minimum": 0 },
      "timeout_s": { "type": "integer", "minimum": 1, "maximum": 1800, "default": 60 }
    },
    "required": ["notebook_id", "cell_index"],
    "additionalProperties": false
  },
  "returns": "{outputs: object[], status: 'ok'|'error'|'timeout', execution_count: int, wall_time_ms: int}"
}
```

### 5. `execute.code`

Execute an ephemeral snippet — does NOT modify the notebook.

```json
{
  "name": "execute.code",
  "description": "Run a one-off snippet against the kernel WITHOUT adding it to the notebook. Use for quick checks, intermediate computations, or things the user shouldn't have to read later. If the user should keep the cell, prefer cells.insert + execute.cell.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": { "type": "string" },
      "code": { "type": "string" },
      "timeout_s": { "type": "integer", "minimum": 1, "maximum": 1800, "default": 60 }
    },
    "required": ["notebook_id", "code"],
    "additionalProperties": false
  },
  "returns": "{outputs: object[], status: 'ok'|'error'|'timeout', wall_time_ms: int}"
}
```

### 6. `execute.cancel`

Interrupt a running cell.

```json
{
  "name": "execute.cancel",
  "description": "Interrupt the currently-running cell in the kernel (SIGINT-equivalent). Use when execute.cell or execute.code timed out, or when the agent realizes it kicked off something that shouldn't run to completion.",
  "inputSchema": {
    "type": "object",
    "properties": { "notebook_id": { "type": "string" } },
    "required": ["notebook_id"],
    "additionalProperties": false
  },
  "returns": "{interrupted: bool, was_busy: bool}"
}
```

### 7. `kernel.list_variables`

Names + types + sizes — never values. The cheap discovery tool.

```json
{
  "name": "kernel.list_variables",
  "description": "List user-defined variables in the kernel — names, types, sizes, shapes only. NEVER returns values. Use this to discover what's in the kernel before calling inspect on something specific. Filters out builtins and IPython internals.",
  "inputSchema": {
    "type": "object",
    "properties": { "notebook_id": { "type": "string" } },
    "required": ["notebook_id"],
    "additionalProperties": false
  },
  "returns": "Array<{name: string, type: string, size_bytes?: int, shape?: int[], summary?: string}>"
}
```

### 8. `inspect` — the polymorphic introspection tool

The differentiation tool. Three modes carry three privacy postures.

```json
{
  "name": "inspect",
  "description": "Inspect a kernel value. `target` is a variable name OR a Python expression (e.g. 'df.dtypes', 'len(rows)'). Mode controls how much is returned:\n  - 'auto' (default, SAFE): type-aware summary. DataFrame → shape+dtypes+head(5). ndarray → shape+dtype+head. Scalar/short repr → repr capped at 1KB.\n  - 'summary' (SAFE): DataFrame.describe() + top-K value_counts for low-cardinality categoricals. ndarray → stats.\n  - 'value' (UNSAFE): raw repr capped at 50KB. WARNING: may contain sensitive data (PII, secrets, customer values). ONLY use when the user explicitly asks to see actual values.\nDefault to 'auto'. Escalate to 'summary' for richer statistics. Escalate to 'value' only on explicit user ask.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": { "type": "string" },
      "target": { "type": "string", "description": "Variable name or Python expression to inspect" },
      "mode": { "type": "string", "enum": ["auto", "summary", "value"], "default": "auto" }
    },
    "required": ["notebook_id", "target"],
    "additionalProperties": false
  },
  "returns": "{mode_used: string, target_type: string, summary: object, truncated: bool, bytes_dropped?: int}"
}
```

### 9. `plots.capture_last`

The wow moment of the killer demo.

```json
{
  "name": "plots.capture_last",
  "description": "Return the most recently rendered plot from the kernel as a base64 PNG. Works for matplotlib (inline backend — default), plotly (requires kaleido), and altair. Returns null if no plot has been rendered since kernel start or last reset.",
  "inputSchema": {
    "type": "object",
    "properties": { "notebook_id": { "type": "string" } },
    "required": ["notebook_id"],
    "additionalProperties": false
  },
  "returns": "{image_png_base64: string, source: 'matplotlib'|'plotly'|'altair'|'unknown', cell_index?: int} | null"
}
```

### 10. `debug.last_traceback`

```json
{
  "name": "debug.last_traceback",
  "description": "Return the most recent exception raised in the kernel, with a formatted traceback. Returns null if no error has occurred since the kernel started or the last reset. Use this when execute.cell or execute.code returned status='error' and you need the details.",
  "inputSchema": {
    "type": "object",
    "properties": { "notebook_id": { "type": "string" } },
    "required": ["notebook_id"],
    "additionalProperties": false
  },
  "returns": "{ename: string, evalue: string, traceback: string[], cell_index?: int} | null"
}
```

## What's NOT in v1 (and where it might go)

| Tool | Why it's out of v1 | Likely home |
| --- | --- | --- |
| `notebooks.list_all(path)` | Beyond the killer demo. Filesystem listing isn't the agent's bottleneck. | v1.1, with a path filter. |
| `notebooks.open(path)` | Server-mode users open notebooks in Lab themselves. Standalone-mode handles it via CLI. | v1.1 if asked. |
| `notebooks.save(path)` | REST PUT happens implicitly on cells.* edits. | Never as a separate tool. |
| `cells.read` (single) | Subsumed by `cells.read_recent(n=1)`. | Never. |
| `cells.read_all` | A 200-cell notebook destroys context. Force the agent to grep / read_recent. | Reconsider with a `range:` param at v1.1. |
| `cells.edit`, `cells.delete` | The agent can prefix-insert a corrected cell, which is less destructive and aligns with the privacy/safety stance. | v1.1, behind a `--enable-destructive-edits` flag. |
| `kernel.restart` | Nuclear option — user can do it in Lab. Not killer-demo-critical. | v1.1. |
| `kernel.status` | Returned as a field in `notebooks.list_open`. | Already shipped via #1. |
| `plots.list_recent(n)` | The agent rarely needs more than the last one. | v1.1 if requested. |

## Total cost-benefit accounting

10 tools × strong schemas × privacy-aware defaults. Under the 20-tool soft cap from the master prompt. Tunable without breaking the killer demo. If agent quality degrades with this many, the first cut is collapsing `execute.cell` + `execute.code` + `execute.cancel` into a polymorphic `execute(mode)` — down to 8. Leave that as a v1.5 lever.
