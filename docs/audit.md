# Audit log

> **Status: planned, not yet implemented.** The `PrivacyConfig.audit_log`
> config field exists and is loaded, but no tool currently emits to it. This
> doc describes the v0.1 design — it ships in v0.2. Tracked as a Phase-3
> roadmap item. See [Phase 3 roadmap](#) section "Carry-over from audit."

mcp-jupyter-kernel will log every tool call to a JSON-lines file for privacy review.

**Default: off.** Tool calls don't write anywhere. Enable explicitly (once shipped).

## Enabling

Config-file:

```yaml
privacy:
  audit_log: ./mcp-jupyter-kernel-audit.jsonl
```

Or CLI: `--audit-log ./mcp-jupyter-kernel-audit.jsonl`.

## What gets logged

One JSON object per line:

```json
{
  "ts": "2026-05-13T14:23:01.123Z",
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

Field by field:

| Field | Meaning |
| --- | --- |
| `ts` | RFC3339 timestamp in UTC. |
| `tool` | Tool name (e.g. `inspect`, `execute.cell`). |
| `notebook_id` | Session ID (server mode) or `"local"` (standalone). |
| `args` | Tool arguments **with raw values truncated**. For `inspect mode=value`, the target string is logged but the returned value is not. |
| `status` | `ok` / `error` / `timeout`. |
| `returned_bytes` | Byte length of the response payload. |
| `wall_time_ms` | Total tool execution time, end-to-end. |
| `redactions_applied` | Count of pattern-based redactions on the returned text. |
| `truncated` | Whether the response was truncated to fit the 50 KB cap. |

## What does NOT get logged

- Raw returned values. Even for `inspect mode=value` calls, the *output* is not in the audit log — only the call metadata. The audit log is for "what tools the agent invoked," not "what the agent saw."
- Authentication tokens.
- Other notebooks in the same Jupyter server. Each session is logged independently.

If you DO want returned values logged (e.g. for compliance retention), that's currently out of scope. File an issue.

## Reviewing the log

Plain JSON lines, so:

```bash
# How many tool calls today?
jq -r 'select(.ts | startswith("2026-05-13"))' audit.jsonl | wc -l

# Tools that returned the most bytes
jq -r '"\(.returned_bytes) \(.tool)"' audit.jsonl | sort -rn | head

# Every inspect call with mode=value (the explicit raw-data path)
jq 'select(.tool == "inspect" and .args.mode == "value")' audit.jsonl
```

## Rotation

mcp-jupyter-kernel does not rotate the log. Use `logrotate` (Linux), a scheduled task (Windows), or `launchd` (macOS). The file is append-only and safe to truncate/rotate while the server is running.

## Failure mode

If the audit log path becomes unwritable mid-session (disk full, permissions changed), the tool call still succeeds and the failure is surfaced once via stderr. We deliberately do NOT fail the tool call — losing audit visibility is bad, but breaking the user's workflow because of it is worse.
