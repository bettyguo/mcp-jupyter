# Data handling implementation

> Implementation companion to [privacy.md](privacy.md). What the inspection tools actually do at runtime.

## The inspect tool — mode dispatch

```
inspect(notebook_id, target, mode='auto')
```

The agent passes `target` as either a variable name (`"customer_df"`) or a Python expression (`"customer_df.dtypes"`). We don't try to parse the expression ourselves — we send it to the kernel via `execute.code` with `silent=True, store_history=False` (so it doesn't count toward `execution_count`).

### Mode = auto

The kernel-side helper inspects `type(target_value)` and dispatches:

| Type | Returns |
| --- | --- |
| `pandas.DataFrame` | `{kind: 'dataframe', shape, dtypes (dict<col,str>), head: 5 rows as list-of-dicts, memory_usage_bytes, columns}` |
| `pandas.Series` | `{kind: 'series', len, dtype, head: 5 values, memory_usage_bytes, name}` |
| `numpy.ndarray` | `{kind: 'ndarray', shape, dtype, nbytes, head: first 5 along axis 0 as list}` |
| `torch.Tensor` (if torch present) | `{kind: 'tensor', shape, dtype, device, requires_grad, head: first 5 along axis 0 as list}` |
| `dict` | `{kind: 'dict', len, key_sample: first 10 keys, value_type_sample: type of first value}` |
| `list`/`tuple` | `{kind: 'sequence', len, item_type_sample, head: first 5 items as repr-capped strings}` |
| `str` | `{kind: 'str', len, head_chars: first 200 chars}` |
| other | `{kind: 'other', type, repr: capped at 1KB}` |

The kernel-side helper is delivered by a small bootstrap snippet (`__mjk_helpers`) that we execute once at attach. Failure to bootstrap (e.g., on a non-Python kernel) → fall back to `repr(target)` capped at 1 KB.

### Mode = summary

| Type | Returns |
| --- | --- |
| `pandas.DataFrame` | `{kind: 'dataframe_summary', describe: describe(include='all') as dict, value_counts: dict<col, top-10> for cols where nunique() ≤ 50}` |
| `pandas.Series` | `{kind: 'series_summary', describe: describe() as dict, value_counts: top-10 if nunique() ≤ 50}` |
| `numpy.ndarray` | `{kind: 'ndarray_summary', stats: {min, max, mean, std, percentiles: [25, 50, 75], nan_count}}` |
| other | error: `'summary mode requires DataFrame, Series, or ndarray'` |

### Mode = value

`repr(target_value)` capped at 50 KB. The tool description carries the warning text that gets surfaced to the LLM:

> WARNING: mode='value' returns raw kernel values which may contain sensitive data (PII, secrets, customer values). ONLY use when the user explicitly asks to see actual values.

We do NOT log the value text into the audit log — only the call metadata. (If the user enabled the audit log AND wants the full call payload, that's a separate `audit_log.full_payload: true` opt-in, defaulting off.)

## Kernel-side helper bootstrap

Once per kernel session, we inject a helper module:

```python
# __mjk_helpers (executed silent=True, store_history=False)
import json, sys, math

class _MjkHelpers:
    @staticmethod
    def inspect_auto(name_or_expr):
        # Resolve name first, fall back to eval for expressions.
        try:
            val = eval(name_or_expr, sys.modules['__main__'].__dict__)
        except NameError:
            return {"error": "not_found", "target": name_or_expr}
        return _MjkHelpers._summarize(val)

    @staticmethod
    def _summarize(val):
        # ... type dispatch as above ...
        ...

__mjk = _MjkHelpers
```

Tool handlers then send `execute.code` requests like `__mjk.inspect_auto("customer_df")` and parse the JSON reply from the `execute_result` payload.

Helper-failure modes:

- Kernel was restarted → helper gone. The first tool call after restart re-bootstraps automatically (cheap; ~10 ms).
- Non-Python kernel (R, Julia) → bootstrap fails. We fall back to `repr(target)` via the kernel's native facilities. Tool returns `mode_used: 'fallback'` and a noisier shape.

## kernel.list_variables — the cheap discovery tool

Implementation: same helper, dispatched to:

```python
def list_variables():
    user_ns = sys.modules['__main__'].__dict__
    out = []
    for name, val in user_ns.items():
        if name.startswith('_') or name in IPYTHON_BUILTINS or name == '__mjk':
            continue
        out.append({
            "name": name,
            "type": type(val).__name__,
            "size_bytes": _safe_sizeof(val),
            "shape": _safe_shape(val),
            "summary": _one_line_summary(val),  # never the value itself
        })
    return out
```

Notice: `summary` is a one-line text fragment like `"DataFrame[10000×6]"`, never an actual value. This is the rule.

## Output redaction (planned for v0.2)

> **Status:** the `redact()` function exists and is unit-tested in
> `src/mcp_jupyter_kernel/helpers/redact.py`, but no tool currently
> calls it. The pipeline described here is the v0.2 target.

When wired, the redactor runs on every tool's text fields before returning to the agent:

- AWS keys: `AKIA[0-9A-Z]{16}` → `<REDACTED:aws_key>`
- Anthropic/OpenAI keys: `sk-[A-Za-z0-9_\-]{20,}` → `<REDACTED:llm_key>`
- Generic keyed secrets: `(key|token|secret|password|api[_-]?key)["\s:=]+[\'"]?[A-Za-z0-9_\-]{16,}` → `<REDACTED:secret>`
- JWTs: `eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+` → `<REDACTED:jwt>`

Disabled with `privacy.redact_secrets: false`.

This is heuristic; we document it as such. Determined leakage gets through.

## Size caps

| Cap | Value | Behavior on overflow |
| --- | --- | --- |
| Per-tool response | 50 KB (configurable) | Trim text fields; set `truncated: true`, `bytes_dropped: N` |
| `head` size | 5 (per inspect) | Hard limit at 100, configurable per-call |
| `kernel.list_variables` count | 200 | Sort by size desc; truncate to 200; flag `truncated: true` |
| `inspect` value-mode | 50 KB hard cap | `truncated: true` |

Truncation is always visible to the agent — we never silently drop data.

## Audit log entry shape (planned for v0.2)

> **Status:** config field `privacy.audit_log` is parsed; no code emits.
> Target schema below.

When `privacy.audit_log: <path>` is set, every tool call will append a JSON line:

```json
{
  "ts": "2026-05-13T14:23:01.123Z",
  "tool": "inspect",
  "notebook_id": "abc",
  "args": {"target": "customer_df", "mode": "auto"},
  "status": "ok",
  "returned_bytes": 1234,
  "wall_time_ms": 42,
  "redactions_applied": 0,
  "truncated": false
}
```

Note: `args` is captured **with values redacted/truncated** — we don't want the audit log to itself become a data-leak vector. `inspect` in mode=`value` records the args (target + mode) but not the returned value.
