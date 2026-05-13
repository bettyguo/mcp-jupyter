"""Shared test fixtures.

Three kinds of tests:
  - **Unit / structural** — no kernel, no server. Run on every commit.
  - **Integration (standalone-mode)** — spawns a real python3 kernel.
    Marked `@pytest.mark.integration_standalone`; requires `ipykernel`.
  - **Integration (server-mode)** — needs a running jupyter_server. Marked
    `@pytest.mark.integration_server`. Three sources, in priority order:
      1. `JUPYTER_TEST_URL` + `JUPYTER_TEST_TOKEN` env vars (CI / Docker sidecar).
      2. `MCP_JUPYTER_AUTOSPAWN_SERVER=1` triggers a local subprocess spawn.
      3. Otherwise skipped.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration_server: requires jupyter_server (env JUPYTER_TEST_URL or MCP_JUPYTER_AUTOSPAWN_SERVER=1).",
    )
    config.addinivalue_line(
        "markers",
        "integration_standalone: spawns a real python3 kernel; requires ipykernel.",
    )


@pytest.fixture
def sample_notebook_path() -> Path:
    return FIXTURES / "sample_notebook.ipynb"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_jupyter(url: str, token: str, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(
                f"{url}/api", headers={"Authorization": f"token {token}"}
            )
            with urllib.request.urlopen(req, timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"jupyter_server did not become ready at {url} within {timeout_s}s")


@pytest.fixture(scope="session")
def _jupyter_spawned_server() -> Any:
    """Spawn a local jupyter_server subprocess on demand.

    Activates only when `MCP_JUPYTER_AUTOSPAWN_SERVER=1` AND `JUPYTER_TEST_URL`
    is not already set (CI / Docker sidecar takes precedence).
    """
    if os.environ.get("JUPYTER_TEST_URL"):
        yield None
        return
    if os.environ.get("MCP_JUPYTER_AUTOSPAWN_SERVER") != "1":
        yield None
        return

    port = _free_port()
    token = "mjk-test-" + uuid.uuid4().hex[:16]
    runtime_dir = FIXTURES.parent / ".jupyter_runtime"
    runtime_dir.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "jupyter_server",
        f"--port={port}",
        f"--ServerApp.token={token}",
        "--ServerApp.password=",
        "--no-browser",
        "--ServerApp.disable_check_xsrf=True",
        "--ServerApp.allow_origin=*",
        f"--ServerApp.root_dir={runtime_dir}",
        "--ServerApp.open_browser=False",
        "--ServerApp.allow_remote_access=False",
    ]
    env = dict(os.environ)
    env.pop("JUPYTER_TOKEN", None)  # don't inherit a stale token
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True
    )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_jupyter(url, token, timeout_s=30.0)
    except Exception:
        out, err = proc.communicate(timeout=5)
        proc.kill()
        raise RuntimeError(f"failed to start jupyter_server: STDOUT={out!r} STDERR={err!r}") from None
    try:
        yield {"url": url, "token": token, "proc": proc}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture
def jupyter_test_url(_jupyter_spawned_server) -> str:
    if _jupyter_spawned_server:
        return _jupyter_spawned_server["url"]
    url = os.environ.get("JUPYTER_TEST_URL")
    if not url:
        pytest.skip(
            "integration_server: set JUPYTER_TEST_URL+JUPYTER_TEST_TOKEN, "
            "or MCP_JUPYTER_AUTOSPAWN_SERVER=1 to auto-spawn jupyter_server."
        )
    return url


@pytest.fixture
def jupyter_test_token(_jupyter_spawned_server) -> str:
    if _jupyter_spawned_server:
        return _jupyter_spawned_server["token"]
    tok = os.environ.get("JUPYTER_TEST_TOKEN", "")
    if not tok:
        pytest.skip(
            "integration_server: JUPYTER_TEST_TOKEN not set; or set "
            "MCP_JUPYTER_AUTOSPAWN_SERVER=1 to auto-spawn."
        )
    return tok
