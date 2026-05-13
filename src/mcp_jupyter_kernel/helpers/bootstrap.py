"""Kernel-side helper code injected once per session.

Sent via execute_code(silent=True, store_history=False). Provides `__mjk`
namespace used by inspect / kernel.list_variables tools. See
docs/data-handling.md.

Idempotent — safe to re-run after kernel restart.

Naming convention inside the helper: names referenced *inside* the
`_MjkHelpers` class body MUST NOT start with two underscores, because Python
name-mangles `__name` to `_MjkHelpers__name` in that scope — silently breaking
lookups. So we use single-underscore aliases (`_mjk_sys`, `_mjk_ns`) that
survive class-body lookup. Names referenced only at module scope (`__mjk`,
`__mjk_json`) keep their double underscores because they're not subject to
mangling outside a class body, and the extra leading underscore keeps them
out of %whos.
"""

from __future__ import annotations

KERNEL_HELPER_SRC = r"""
import json as __mjk_json
import sys as _mjk_sys

def _mjk_ns():
    # In an IPython kernel, user variables live in get_ipython().user_ns —
    # NOT in sys.modules['__main__'].__dict__ (that's the InteractiveShell's
    # own dict). Fall back to __main__ for non-IPython kernels.
    try:
        return get_ipython().user_ns  # noqa: F821
    except (NameError, AttributeError):
        return _mjk_sys.modules['__main__'].__dict__

class _MjkHelpers:
    _IPY_BUILTINS = {
        'In', 'Out', 'exit', 'quit', 'get_ipython',
        '__mjk', '__mjk_json', '_mjk_sys', '_mjk_ns', '_MjkHelpers',
    }

    @staticmethod
    def _safe_sizeof(v):
        try:
            return _mjk_sys.getsizeof(v)
        except Exception:
            return None

    @staticmethod
    def _safe_shape(v):
        for attr in ('shape',):
            if hasattr(v, attr):
                try:
                    s = getattr(v, attr)
                    return list(s) if hasattr(s, '__iter__') else None
                except Exception:
                    pass
        return None

    @staticmethod
    def _one_line(v):
        try:
            t = type(v).__name__
            if hasattr(v, 'shape'):
                return f"{t}{tuple(v.shape)!s}"
            if isinstance(v, (list, tuple, dict, set, str, bytes)):
                return f"{t}(len={len(v)})"
            return t
        except Exception:
            return type(v).__name__

    @classmethod
    def list_variables(cls):
        ns = _mjk_ns()
        out = []
        for name, val in ns.items():
            if name.startswith('_') or name in cls._IPY_BUILTINS:
                continue
            out.append({
                'name': name,
                'type': type(val).__name__,
                'size_bytes': cls._safe_sizeof(val),
                'shape': cls._safe_shape(val),
                'summary': cls._one_line(val),
            })
        out.sort(key=lambda r: -(r['size_bytes'] or 0))
        return out

    @classmethod
    def inspect_auto(cls, target, head_size=5):
        try:
            val = eval(target, _mjk_ns())
        except NameError:
            return {'error': 'not_found', 'target': target}
        return cls._summarize_auto(val, head_size)

    @classmethod
    def _summarize_auto(cls, val, head_size):
        try:
            import pandas as pd
            if isinstance(val, pd.DataFrame):
                return {
                    'kind': 'dataframe',
                    'shape': list(val.shape),
                    'dtypes': {c: str(d) for c, d in val.dtypes.items()},
                    'columns': list(val.columns),
                    'head': val.head(head_size).to_dict(orient='records'),
                    'memory_usage_bytes': int(val.memory_usage(deep=True).sum()),
                }
            if isinstance(val, pd.Series):
                return {
                    'kind': 'series',
                    'len': len(val),
                    'dtype': str(val.dtype),
                    'name': val.name,
                    'head': val.head(head_size).tolist(),
                    'memory_usage_bytes': int(val.memory_usage(deep=True)),
                }
        except ImportError:
            pass
        try:
            import numpy as np
            if isinstance(val, np.ndarray):
                return {
                    'kind': 'ndarray',
                    'shape': list(val.shape),
                    'dtype': str(val.dtype),
                    'nbytes': int(val.nbytes),
                    'head': val.ravel()[:head_size].tolist(),
                }
        except ImportError:
            pass
        if isinstance(val, dict):
            keys = list(val.keys())
            return {
                'kind': 'dict',
                'len': len(val),
                'key_sample': keys[:10],
                'value_type_sample': type(val[keys[0]]).__name__ if keys else None,
            }
        if isinstance(val, (list, tuple)):
            head = [repr(x)[:200] for x in list(val)[:head_size]]
            item_type = type(val[0]).__name__ if val else None
            return {
                'kind': 'sequence',
                'len': len(val),
                'item_type_sample': item_type,
                'head': head,
            }
        if isinstance(val, str):
            return {'kind': 'str', 'len': len(val), 'head_chars': val[:200]}
        return {'kind': 'other', 'type': type(val).__name__, 'repr': repr(val)[:1024]}

    @classmethod
    def inspect_summary(cls, target):
        try:
            val = eval(target, _mjk_ns())
        except NameError:
            return {'error': 'not_found', 'target': target}
        try:
            import pandas as pd
            if isinstance(val, (pd.DataFrame, pd.Series)):
                desc = val.describe(include='all').to_dict()
                vc = {}
                cols = val.columns if isinstance(val, pd.DataFrame) else [val.name]
                src = val if isinstance(val, pd.DataFrame) else pd.DataFrame({val.name: val})
                for c in cols:
                    try:
                        if src[c].nunique(dropna=True) <= 50:
                            vc[str(c)] = src[c].value_counts().head(10).to_dict()
                    except Exception:
                        pass
                return {'kind': type(val).__name__.lower() + '_summary', 'describe': desc, 'value_counts': vc}
        except ImportError:
            pass
        try:
            import numpy as np
            if isinstance(val, np.ndarray):
                return {
                    'kind': 'ndarray_summary',
                    'stats': {
                        'min': float(np.nanmin(val)) if val.size else None,
                        'max': float(np.nanmax(val)) if val.size else None,
                        'mean': float(np.nanmean(val)) if val.size else None,
                        'std': float(np.nanstd(val)) if val.size else None,
                        'percentiles': [float(x) for x in np.nanpercentile(val, [25, 50, 75])] if val.size else None,
                        'nan_count': int(np.isnan(val).sum()) if val.dtype.kind == 'f' else 0,
                    },
                }
        except ImportError:
            pass
        return {'error': "summary mode requires DataFrame, Series, or ndarray"}

    @classmethod
    def inspect_value(cls, target, cap_bytes=51200):
        try:
            val = eval(target, _mjk_ns())
        except NameError:
            return {'error': 'not_found', 'target': target}
        r = repr(val)
        encoded = r.encode('utf-8')
        if len(encoded) <= cap_bytes:
            return {'repr': r, 'truncated': False}
        return {
            'repr': encoded[:cap_bytes].decode('utf-8', errors='ignore'),
            'truncated': True,
            'bytes_dropped': len(encoded) - cap_bytes,
        }


__mjk = _MjkHelpers
"""


def helper_call(method: str, *args: object) -> str:
    """Build a kernel-side expression that calls one of the helpers and emits JSON."""
    parts = [repr(a) for a in args]
    return f"print(__mjk_json.dumps(__mjk.{method}({', '.join(parts)})))"
