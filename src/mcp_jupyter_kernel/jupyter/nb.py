"""nbformat helpers for reading, validating and modifying .ipynb files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import nbformat


def read_notebook(path: str | Path) -> Any:
    """Read and validate a notebook file."""
    nb = nbformat.read(str(path), as_version=4)
    nbformat.validate(nb)
    return nb


def write_notebook(nb: Any, path: str | Path) -> None:
    """Atomic write via tempfile + replace."""
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    nbformat.write(nb, str(tmp))
    tmp.replace(p)


def new_code_cell(source: str) -> Any:
    return nbformat.v4.new_code_cell(source=source)


def new_markdown_cell(source: str) -> Any:
    return nbformat.v4.new_markdown_cell(source=source)


def new_notebook(metadata: dict[str, Any] | None = None) -> Any:
    return nbformat.v4.new_notebook(metadata=metadata or {})


def to_outputs(raw: list[dict[str, Any]]) -> list[Any]:
    """Convert plain dict outputs into nbformat NotebookNode form.

    Our ExecutionState produces plain dicts (so the collector has no
    dependency on nbformat). Before writing them back into a notebook on
    disk, nbformat.write needs NotebookNode-shaped entries with attribute
    access (it does `output.output_type` not `output['output_type']`).
    """
    return [nbformat.from_dict(o) for o in raw]
