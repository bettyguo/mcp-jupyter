# Authentication

Server mode only. Standalone mode has no auth (the kernel is a child of
the MCP server itself).

## Config schema

`mcp-jupyter-kernel.yaml`, resolved via `--config`, the
`MCP_JUPYTER_KERNEL_CONFIG` env var, or `./mcp-jupyter-kernel.yaml`:

```yaml
jupyter:
  url: http://localhost:8888
  token: ${JUPYTER_TOKEN}        # ${ENV} interpolation; literal also accepted
  base_url_prefix: ""            # JupyterHub: /user/<name> (no trailing slash)
  ws_subprotocol: "v1.kernel.websocket.jupyter.org"
  verify_tls: true

server:
  transport: stdio               # stdio | http
  host: 127.0.0.1
  port: 8765

privacy:
  default_truncate_bytes: 51200
  head_size: 5
  audit_log: null                # path to enable JSONL audit logging (planned)
  redact_secrets: true           # planned
```

CLI overrides take precedence: `--url`, `--token`, `--token-env`,
`--config`.

## Auth flow

1. Resolve the token: CLI override, then config (with `${VAR}`
   interpolation), then env.
2. REST requests carry `Authorization: token <TOKEN>`. This header
   bypasses XSRF.
3. The WebSocket upgrade either passes the same header or falls back to
   `?token=<TOKEN>` in the URL (some `websockets` versions don't let you
   set handshake headers cleanly).

## JupyterHub

Each user's server is mounted at `/user/<name>/`. Set
`base_url_prefix: /user/<name>` and use a Hub-issued API token with
`access:servers!user=<name>` scope, or a per-server token. Requests then
go to `<url><base_url_prefix>/api/...`.

## What this does not cover

- Password auth. Token-only.
- SSO / OIDC. Put it behind a proxy that accepts a service token.
- mTLS. That's the upstream's problem; we just want a valid cert chain.

## Token handling

The token is held in the config object in memory; never written to disk
or stdout. The startup banner says `auth: token from <env var name>`,
never the value.
