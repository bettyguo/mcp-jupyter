"""Heuristic secret redaction. Best-effort; documented as such in privacy.md."""

from __future__ import annotations

import re

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED:aws_key>"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "<REDACTED:llm_key>"),
    (
        re.compile(
            r"(?i)(key|token|secret|password|api[_-]?key)[\"\s:=]+[\"']?([A-Za-z0-9_\-]{16,})"
        ),
        r"\1=<REDACTED:secret>",
    ),
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
        "<REDACTED:jwt>",
    ),
)


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, number_of_replacements)."""
    count = 0
    for pat, repl in _PATTERNS:
        text, n = pat.subn(repl, text)
        count += n
    return text, count


def truncate(text: str, cap_bytes: int) -> tuple[str, bool, int]:
    """Truncate to cap_bytes (UTF-8). Returns (text, was_truncated, bytes_dropped)."""
    encoded = text.encode("utf-8")
    if len(encoded) <= cap_bytes:
        return text, False, 0
    dropped = len(encoded) - cap_bytes
    return encoded[:cap_bytes].decode("utf-8", errors="ignore"), True, dropped
