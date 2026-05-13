# Tool reference

10 tools across 6 namespaces. Standalone mode and server mode expose the
same surface; the transport below is swappable.

## Conventions

- Return payloads are capped at 50 KB. On overflow the response carries
  `truncated: true` plus a count of bytes dropped.
- `notebook_id` is the session ID from `/api/sessions` in server mode, or
  the literal string `"local"` in standalone mode.
- Tool descriptions are written for agents and lead with what the tool
  does; negative guidance ("don't use for X") is included where eager
  agents would otherwise over-call.

## `notebooks.list_open`

Lists notebooks currently open in the Jupyter session. Call first to find
the `notebook_id` for the other tools. Standalone mode returns one entry.

```json
{
  "inputSchema": {"type": "object", "properties": {}, "additionalProperties": false},
  "returns": "Array<{notebook_id: string, path: string, kernel_id: string, kernel_status: 'idle'|'busy'|'starting'|'dead', last_activity: string}>"
}
```

## `cells.read_recent`

Reads the last N cells (default 5).

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": {"type": "string"},
      "n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}
    },
    "required": ["notebook_id"]
  },
  "returns": "Array<{index: int, cell_type, source: string, outputs?: object[], execution_count?: int}>"
}
```

## `cells.insert`

Inserts a cell after `after_index` (use `-1` to insert at the top). In
server mode the operation is RTC-aware: it reads, checks `last_modified`,
and refuses on conflict.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": {"type": "string"},
      "after_index": {"type": "integer", "minimum": -1},
      "code": {"type": "string"},
      "cell_type": {"type": "string", "enum": ["code", "markdown"], "default": "code"}
    },
    "required": ["notebook_id", "after_index", "code"]
  },
  "returns": "{new_index: int} | {error: 'conflict', detail: string}"
}
```

## `execute.cell`

Executes the cell at `cell_index`. Outputs are persisted in the notebook
AND returned. Default timeout 60s; hard ceiling 1800s.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": {"type": "string"},
      "cell_index": {"type": "integer", "minimum": 0},
      "timeout_s": {"type": "integer", "minimum": 1, "maximum": 1800, "default": 60}
    },
    "required": ["notebook_id", "cell_index"]
  },
  "returns": "{outputs: object[], status: 'ok'|'error'|'timeout', execution_count: int, wall_time_ms: int}"
}
```

## `execute.code`

Runs a one-off snippet against the kernel without adding it to the
notebook. Use for quick checks; use `cells.insert` + `execute.cell` if the
user should keep the cell.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": {"type": "string"},
      "code": {"type": "string"},
      "timeout_s": {"type": "integer", "minimum": 1, "maximum": 1800, "default": 60}
    },
    "required": ["notebook_id", "code"]
  },
  "returns": "{outputs: object[], status: 'ok'|'error'|'timeout', wall_time_ms: int}"
}
```

## `execute.cancel`

SIGINT-equivalent. Interrupts the currently running cell.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {"notebook_id": {"type": "string"}},
    "required": ["notebook_id"]
  },
  "returns": "{interrupted: bool, was_busy: bool}"
}
```

## `kernel.list_variables`

Names, types, sizes and shapes of user-defined variables. Never returns
values. Filters builtins and IPython internals.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {"notebook_id": {"type": "string"}},
    "required": ["notebook_id"]
  },
  "returns": "Array<{name: string, type: string, size_bytes?: int, shape?: int[], summary?: string}>"
}
```

## `inspect`

Inspects a kernel value. `target` is a variable name or any Python
expression (e.g. `df.dtypes`, `len(rows)`).

| Mode | Returns | Privacy posture |
| ---- | ------- | --------------- |
| `auto` (default) | type-aware summary: DataFrame → shape, dtypes, head(5); ndarray → shape, dtype, head; other → repr capped at 1KB | safe |
| `summary` | DataFrame.describe() + top-K value_counts for low-cardinality categoricals; ndarray → stats | safe |
| `value` | raw repr, capped at 50 KB | sensitive: may contain PII or secrets |

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "notebook_id": {"type": "string"},
      "target": {"type": "string"},
      "mode": {"type": "string", "enum": ["auto", "summary", "value"], "default": "auto"}
    },
    "required": ["notebook_id", "target"]
  },
  "returns": "{mode_used: string, summary: object}"
}
```

The tool description tells agents to default to `auto` and escalate only
on explicit user request.

## `plots.capture_last`

Returns the most recently rendered plot from the kernel as a base64 PNG.
Works for matplotlib (inline backend), plotly (requires kaleido), and
altair. `null` if nothing has been rendered since kernel start.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {"notebook_id": {"type": "string"}},
    "required": ["notebook_id"]
  },
  "returns": "{image_png_base64: string, source: 'matplotlib'|'plotly'|'altair'|'unknown', cell_index?: int} | null"
}
```

## `debug.last_traceback`

Returns the most recent exception raised in the kernel with formatted
traceback. Use after `execute.*` returned `status='error'`.

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {"notebook_id": {"type": "string"}},
    "required": ["notebook_id"]
  },
  "returns": "{ename: string, evalue: string, traceback: string[], cell_index?: int} | null"
}
```

## Deliberately not in v1

| Tool | Rationale |
| --- | --- |
| `notebooks.list_all(path)` | Filesystem listing isn't the agent's bottleneck. |
| `notebooks.open(path)` | Server-mode users open notebooks in Lab; standalone-mode handles via CLI. |
| `cells.read` (single) | Use `cells.read_recent(n=1)`. |
| `cells.read_all` | A 200-cell notebook destroys context. |
| `cells.edit`, `cells.delete` | Less destructive to prefix-insert a corrected cell. Possible behind a flag later. |
| `kernel.restart` | User does it in Lab. Possible later. |
| `kernel.status` | Already returned in `notebooks.list_open`. |
| `plots.list_recent(n)` | The agent rarely needs more than one. |
