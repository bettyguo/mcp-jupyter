# Installing mcp-jupyter-kernel

Pre-alpha. APIs may change before v1. **Not yet published to PyPI.**

## Install the binary

From source (current path):

```bash
git clone https://github.com/bettyguo/mcp-jupyter.git
cd mcp-jupyter
pip install -e .
```

Once we publish to PyPI:

```bash
pip install mcp-jupyter-kernel
```

Verify:

```bash
mcp-jupyter-kernel version
```

## Wire it into your MCP client

`mcp-jupyter-kernel mcp install` writes the config for you. Pick your client:

### Claude Desktop

```bash
mcp-jupyter-kernel mcp install --client claude-desktop \
  --mode server --jupyter-url http://localhost:8888 --token-env JUPYTER_TOKEN
```

This updates `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), `%APPDATA%\Claude\claude_desktop_config.json` (Windows), or `~/.config/Claude/claude_desktop_config.json` (Linux). Existing servers are preserved.

Restart Claude Desktop after install.

### Cursor

```bash
mcp-jupyter-kernel mcp install --client cursor \
  --mode server --jupyter-url http://localhost:8888 --token-env JUPYTER_TOKEN
```

Writes `~/.cursor/mcp.json`. Restart Cursor.

### Claude Code (CLI)

Claude Code uses its own `claude mcp add` command. Run:

```bash
mcp-jupyter-kernel mcp install --client claude-code \
  --mode server --jupyter-url http://localhost:8888
```

This prints the exact `claude mcp add ...` command to copy-paste.

### All clients at once

```bash
mcp-jupyter-kernel mcp install --client all --mode server \
  --jupyter-url http://localhost:8888 --token-env JUPYTER_TOKEN
```

## Server mode vs standalone mode

**Server mode** (default): attach to a running Jupyter Lab / Notebook 7 / JupyterHub.

```bash
export JUPYTER_TOKEN=mysecret
jupyter lab --ServerApp.token=$JUPYTER_TOKEN --no-browser   # in another shell
mcp-jupyter-kernel serve --url http://localhost:8888 --token-env JUPYTER_TOKEN
```

**Standalone mode**: spawn a kernel directly; no Jupyter server needed.

```bash
mcp-jupyter-kernel standalone --notebook ./my_analysis.ipynb
```

Useful for headless / CI / sandboxed agent runs. State is in-memory unless you pass `--notebook` (then we write back atomically).

To install with standalone mode:

```bash
mcp-jupyter-kernel mcp install --client claude-desktop --mode standalone \
  --notebook /absolute/path/to/notebook.ipynb
```

## Config file

If you'd rather not pass flags every time, create `mcp-jupyter-kernel.yaml`:

```yaml
jupyter:
  url: http://localhost:8888
  token: ${JUPYTER_TOKEN}        # env-var interpolation
  base_url_prefix: ""            # for JupyterHub: /user/<name>

server:
  transport: stdio

privacy:
  default_truncate_bytes: 51200
  head_size: 5
  redact_secrets: true
  audit_log: null                # set to a path to enable
```

Point at it with `--config ./mcp-jupyter-kernel.yaml` or set `MCP_JUPYTER_KERNEL_CONFIG=./mcp-jupyter-kernel.yaml`.

Full config schema: [auth.md](auth.md).

## Verifying the install

After installing into a client, the 10 tools should appear in your agent:

| Category | Tool |
| --- | --- |
| Notebooks | `notebooks.list_open` |
| Cells | `cells.read_recent`, `cells.insert` |
| Execute | `execute.cell`, `execute.code`, `execute.cancel` |
| Kernel | `kernel.list_variables` |
| Inspect | `inspect` (modes: `auto` / `summary` / `value`) |
| Plots | `plots.capture_last` |
| Debug | `debug.last_traceback` |

Try: open a notebook in Lab, then ask your agent "what tools do you have for Jupyter?" — it should mention the above.

## Troubleshooting

### "No Jupyter token configured"

Set `JUPYTER_TOKEN` in your environment (or whichever env var you used with `--token-env`), or pass `--token` explicitly. The token comes from Jupyter Lab's startup banner or `jupyter server list`.

### Tools don't appear after install

- Restart your MCP client. Most clients only read MCP configs on launch.
- Check `mcp-jupyter-kernel mcp show --client <name>` — it tells you the config path. Open it; you should see your entry under `mcpServers`.

### Server mode says "could not connect"

- Verify your Jupyter URL: `curl http://localhost:8888/api?token=$JUPYTER_TOKEN`.
- Check `--base-url-prefix` if you're on JupyterHub (`/user/<name>`).

### "IOPub data rate exceeded" warnings

Jupyter Server caps output rates by default. For notebooks that produce lots of output, raise `iopub_data_rate_limit` on the server side. mcp-jupyter-kernel can't change it for you (out of scope).

### Windows: `ProactorEventLoop does not implement add_reader`

Cosmetic warning from ZMQ. Standalone mode automatically switches to `WindowsSelectorEventLoopPolicy` at startup. Server mode is unaffected.

## Uninstall

Remove the entry by hand from the client's config file (path shown by `mcp-jupyter-kernel mcp show --client <name>`), then `pip uninstall mcp-jupyter-kernel`. We don't bundle an `mcp uninstall` command yet.
