"""KernelSession: the abstraction the tool layer talks to.

Two implementations: ServerSession (REST + WS against a running
jupyter_server) and StandaloneSession (AsyncKernelManager subprocess).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecuteResult:
    outputs: list[dict[str, Any]]
    status: str  # 'ok' | 'error' | 'timeout'
    execution_count: int | None
    wall_time_ms: int


@dataclass
class NotebookHandle:
    notebook_id: str
    path: str | None
    kernel_id: str
    kernel_status: str  # 'idle' | 'busy' | 'starting' | 'dead'
    last_activity: str | None


class KernelSession(ABC):
    """Common interface for server-mode and standalone-mode kernel access."""

    @abstractmethod
    async def list_notebooks(self) -> list[NotebookHandle]: ...

    @abstractmethod
    async def read_cells(self, notebook_id: str, n: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def insert_cell(
        self,
        notebook_id: str,
        after_index: int,
        code: str,
        cell_type: str = "code",
    ) -> int: ...

    @abstractmethod
    async def execute_cell(
        self,
        notebook_id: str,
        cell_index: int,
        timeout_s: int,
    ) -> ExecuteResult: ...

    @abstractmethod
    async def execute_code(
        self,
        notebook_id: str,
        code: str,
        timeout_s: int,
        silent: bool = False,
    ) -> ExecuteResult: ...

    @abstractmethod
    async def cancel(self, notebook_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def close(self) -> None: ...

    def get_last_plot(self) -> dict[str, Any] | None:
        """Most recently captured plot. Default: no plot."""
        return None

    def get_last_error(self) -> dict[str, Any] | None:
        """Most recent error. Default: no error."""
        return None
