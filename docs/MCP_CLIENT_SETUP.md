# MCP Client Setup (Generic)

This project exposes a local MCP server over STDIO. Any MCP-capable client that
speaks JSON-RPC over a `Content-Length` framed STDIO transport can use it. Codex
is one possible client, not a requirement.

## Install

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

After installation this command should be available:

```bash
kdenlive-mcp
```

## STDIO Transport

The server speaks the MCP protocol over standard input/output with the
`Content-Length` framing used by MCP STDIO transports:

```text
client <-> stdin/stdout <-> kdenlive-mcp
```

No network port is opened by the server. The server only runs as a child process
of the MCP client.

## Generic Client Configuration

Register the server in the MCP client with:

```toml
[mcp_servers.kdenlive]
command = "kdenlive-mcp"
args = []

[mcp_servers.kdenlive.env]
KDENLIVE_MCP_ALLOWED_MEDIA_DIRS = "/home/usuario/Videos"
KDENLIVE_MCP_ALLOWED_PROJECT_DIRS = "/home/usuario/Videos:/data/PROYECTOS/kdenlive-mcp/examples/recon"
KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS = "/home/usuario/Videos"
KDENLIVE_MCP_FLATPAK_ID = "org.kde.kdenlive"
KDENLIVE_MCP_LOG_FILE = "/data/PROYECTOS/kdenlive-mcp/logs/kdenlive-mcp.log"
```

A copy is available at:

```text
examples/mcp_client_config.toml
```

The exact TOML key names for the MCP server block vary by client; keep the same
semantics (`command`, `args`, `env` allowlists). Adjust the allowlists before
use: the server should only receive directories where the agent is allowed to
read media or write generated artifacts.

Allowlist categories:

```text
KDENLIVE_MCP_ALLOWED_MEDIA_DIRS     read media
KDENLIVE_MCP_ALLOWED_PROJECT_DIRS   read .kdenlive projects and valid project locations
KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS    write derived files, manifests, backups, locks
KDENLIVE_MCP_FLATPAK_ID             Kdenlive Flatpak id (default org.kde.kdenlive)
KDENLIVE_MCP_LOG_FILE               JSONL tool-call log; "off" disables logging
```

## Minimal Expected Tools

After registration the client can call `tools/list` and should see at least:

```text
health_check
get_environment
scan_media
create_vlog_rough_cut_project
export_timeline_to_kdenlive_template
```

All 60 registered tools are discoverable through the real STDIO channel.

## Verify The Local Setup

Default deterministic checks:

```bash
scripts/dev_check.sh
```

Real STDIO smoke test (starts the server as a subprocess and executes
`initialize` + `tools/list` over the real framing):

```bash
python3 scripts/mcp_stdio_smoke_test.py
```

Or through the dev check:

```bash
KDENLIVE_MCP_RUN_STDIO_SMOKE=1 scripts/dev_check.sh
```

Expected output:

```json
{
  "success": true,
  "server": "kdenlive-mcp",
  "tool_count": 60,
  "required_tools_present": true,
  "error": null
}
```

## Codex As One Example

Codex is supported as a specific example, not as the only client:

```text
docs/CODEX_SETUP.md
examples/codex_mcp_config.toml
```

## Security Note For Cloud Agents

The server is local-first and filesystem-bound. It must run on the machine that
owns the media and projects. If a cloud-hosted agent reaches this server, the
server still runs locally; expose it only through an explicit bridge that the
user decides to create, and keep the allowlists minimal. Never publish the local
allowlists, log file, or media paths to a public surface.
