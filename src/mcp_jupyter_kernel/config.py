"""Configuration models. Single source of truth for the YAML/CLI surface.

See docs/auth.md for the YAML schema. Env-var interpolation (`${VAR}`) is
resolved at load time.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

_ENV_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _interp(value: str) -> str:
    return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)


class JupyterConfig(BaseModel):
    url: str = "http://localhost:8888"
    token: str = ""
    base_url_prefix: str = ""
    ws_subprotocol: str = "v1.kernel.websocket.jupyter.org"
    verify_tls: bool = True
    iopub_data_rate_limit_warning: bool = True

    @field_validator("token", "url", "base_url_prefix", mode="before")
    @classmethod
    def _interp_env(cls, v: str) -> str:
        return _interp(v) if isinstance(v, str) else v


class ServerConfig(BaseModel):
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765


class PrivacyConfig(BaseModel):
    default_truncate_bytes: int = 51_200
    head_size: int = Field(default=5, ge=1, le=100)
    audit_log: str | None = None
    redact_secrets: bool = True


class StandaloneConfig(BaseModel):
    kernel_name: str = "python3"
    cwd: str | None = None
    notebook_path: str | None = None


class Config(BaseModel):
    jupyter: JupyterConfig = Field(default_factory=JupyterConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    standalone: StandaloneConfig = Field(default_factory=StandaloneConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        if path is None:
            env = os.environ.get("MCP_JUPYTER_KERNEL_CONFIG")
            path = env or "./mcp-jupyter-kernel.yaml"
        p = Path(path)
        if not p.exists():
            return cls()
        return cls.model_validate(yaml.safe_load(p.read_text()) or {})
