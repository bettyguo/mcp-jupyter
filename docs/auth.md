# Authentication design

> Server mode only. Standalone mode has no auth — the kernel is a subprocess of the MCP server itself.

## Server-mode config schema

`mcp-jupyter-kernel.yaml` (path resolved via `--config` CLI flag, env var `MCP_JUPYTER_KERNEL_CONFIG`, or `./mcp-jupyter-kernel.yaml`):

```yaml
jupyter:
  url: http://localhost:8888
  token: ${JUPYTER_TOKEN}        # ${ENV} interpolation; literal also accepted
  # Optional:
  base_url_prefix: ""            # for JupyterHub: "/user/myname" (no trailing slash)
  ws_subprotocol: "v1.kernel.websocket.jupyter.org"  # set to "" to force JSON frames
  verify_tls: true
  iopub_data_rate_limit_warning: true  # warn if server caps look like defaults

server:
  transport: stdio               # stdio | http
  host: 127.0.0.1                # http transport only
  port: 8765                     # http transport only

privacy:
  default_truncate_bytes: 51200  # 50 KB cap on tool returns
  head_size: 5
  audit_log: null                # set to a path to enable JSONL audit logging
  redact_secrets: true
```

CLI overrides (highest priority): `--url`, `--token`, `--token-env JUPYTER_TOKEN`, `--config`.

## Auth flow

1. On startup, mcp-jupyter-kernel resolves `jupyter.token` (env interpolation, literal, or CLI override).
2. All REST requests carry `Authorization: token <TOKEN>`. This header bypasses XSRF — we never need to dance with the `_xsrf` cookie.
3. WebSocket upgrade requests pass the same `Authorization` header. Some `httpx`/`websockets` versions can't set headers on the WS handshake; in that case fall back to `?token=<TOKEN>` in the URL.
4. On first attach, GET `/api/status` (or `/api/contents/` if status is unavailable) to validate auth. A 401/403 surfaces as a clear startup error, not a tool-call error.

## JupyterHub

JupyterHub mounts each user's server at `/user/<name>/`. To use mcp-jupyter-kernel with Hub:

```yaml
jupyter:
  url: https://hub.example.com
  base_url_prefix: /user/alanwu
  token: ${JUPYTERHUB_API_TOKEN}
```

The token must be either a Hub-issued API token with `access:servers!user=<name>` scope OR a per-server token. mcp-jupyter-kernel constructs requests as `<url><base_url_prefix>/api/...`.

## WebSocket subprotocol negotiation

Default: send `Sec-WebSocket-Protocol: v1.kernel.websocket.jupyter.org` on the upgrade. If the server echoes it back, use the binary framing (offset-table → channel/header/parent_header/metadata/content/buffers). Otherwise fall back to JSON frames.

Force JSON for debugging: `ws_subprotocol: ""` in config or `--no-binary-ws` on CLI.

## What auth does NOT do

- **No password support.** Token-only. Password auth in Jupyter is a UX wart and modern Jupyter Lab versions generate a token by default.
- **No SSO / OIDC.** If your Jupyter sits behind an SSO proxy, configure it to accept a long-lived service token.
- **No mTLS.** TLS termination is upstream's problem; we just need `verify_tls: true` and a valid cert chain (which the standard `httpx` resolves via `certifi`).

## Where the token is logged or stored

- **Never in stdout/stderr.** The startup banner says "auth: token from <env var name>" not "token: abc123".
- **Audit log (if enabled) records the tool call's `notebook_id` and `kernel_id`, not auth headers.**
- **The token is held in memory in the config object.** No on-disk caching.
