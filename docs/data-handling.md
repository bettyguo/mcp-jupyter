# Data handling

Implementation notes for the `inspect` tool and friends. Companion to
`privacy.md`.

## inspect dispatch

`inspect(notebook_id, target, mode='auto')`. `target` is a variable name
or a Python expression. We send it to the kernel via `execute_code` with
`silent=False, store_history=False` and parse the JSON the helper prints.

### mode = auto

The kernel-side helper dispatches on `type(target_value)`:

| type | shape of returned summary |
| --- | --- |
| `pandas.DataFrame` | `kind: 'dataframe'`, `shape`, `dtypes`, `columns`, `head` (5 rows as list-of-dicts), `memory_usage_bytes` |
| `pandas.Series` | `kind: 'series'`, `len`, `dtype`, `name`, `head` (5 values), `memory_usage_bytes` |
| `numpy.ndarray` | `kind: 'ndarray'`, `shape`, `dtype`, `nbytes`, `head` (first 5 elements ravelled) |
| `dict` | `kind: 'dict'`, `len`, `key_sample` (first 10 keys), `value_type_sample` |
| `list` / `tuple` | `kind: 'sequence'`, `len`, `item_type_sample`, `head` (first 5 items, each repr-capped) |
| `str` | `kind: 'str'`, `len`, `head_chars` (first 200) |
| other | `kind: 'other'`, `type`, `repr` (capped at 1KB) |

### mode = summary

| type | shape of returned summary |
| --- | --- |
| DataFrame / Series | `kind: '*_summary'`, `describe`, `value_counts` (top-10 per column where `nunique <= 50`) |
| ndarray | `kind: 'ndarray_summary'`, `stats: {min, max, mean, std, percentiles, nan_count}` |
| other | `{error: 'summary mode requires DataFrame, Series, or ndarray'}` |

### mode = value

`repr(val)` UTF-8-capped at 50 KB. The tool description warns the LLM
that this may contain sensitive data.

## Helper bootstrap

Once per kernel session we inject a small helper module under the name
`__mjk`. Source is in `src/mcp_jupyter_kernel/helpers/bootstrap.py`.
Roughly:

```python
import json as __mjk_json
import sys as _mjk_sys

def _mjk_ns():
    try:
        return get_ipython().user_ns
    except (NameError, AttributeError):
        return _mjk_sys.modules['__main__'].__dict__

class _MjkHelpers:
    @classmethod
    def inspect_auto(cls, target, head_size=5):
        try:
            val = eval(target, _mjk_ns())
        except NameError:
            return {'error': 'not_found', 'target': target}
        return cls._summarize_auto(val, head_size)
    ...

__mjk = _MjkHelpers
```

Tool handlers send `print(__mjk_json.dumps(__mjk.inspect_auto('df')))`
and read the JSON off iopub stdout.

The aliases inside `_MjkHelpers` deliberately use a single leading
underscore (`_mjk_sys`, `_mjk_ns`): a double underscore inside a class
body is name-mangled to `_ClassName__name`, which silently breaks the
lookup.

### Failure modes

- Kernel restart wipes the helper. The next call re-bootstraps; the
  bootstrap is idempotent.
- Non-Python kernel (R, Julia): the bootstrap will fail. Currently the
  tool returns the raw helper-output error and the agent sees an
  unparseable response. Planned to add native-kernel helpers later.

## kernel.list_variables

Uses the same helper. Returns one entry per user variable with
`{name, type, size_bytes, shape, summary}` where `summary` is a single
short text fragment like `"DataFrame(10000, 6)"`. Never returns values.

Filters: names starting with `_`, IPython builtins (`In`, `Out`, etc.),
and the `__mjk` helper itself.

## Size caps

| cap | value | overflow behaviour |
| --- | --- | --- |
| per-tool response | 50 KB | `truncated: true`, `bytes_dropped: N` |
| `head` size | 5 default, 100 hard limit | configurable per call |
| `inspect` value-mode | 50 KB | `truncated: true` |

## Audit log shape (planned)

When implemented, every tool call will append one JSON line:

```json
{
  "ts": "...",
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

`args` is captured with values redacted; `inspect mode='value'` records
the args but not the returned value.
