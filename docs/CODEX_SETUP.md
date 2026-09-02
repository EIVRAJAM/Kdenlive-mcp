# Codex MCP Setup

This document is a Codex-specific example. For client-agnostic setup, transport
details, and security notes for cloud agents, see `docs/MCP_CLIENT_SETUP.md`
and the generic example `examples/mcp_client_config.toml`. Codex is one possible
MCP client, not a requirement of the system.

## Install

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

After installation, this command should be available:

```bash
kdenlive-mcp
```

## Minimal Codex Configuration

Use this as the MCP server entry:

```toml
[mcp_servers.kdenlive]
command = "kdenlive-mcp"
args = []

[mcp_servers.kdenlive.env]
KDENLIVE_MCP_ALLOWED_MEDIA_DIRS = "/home/abrahamc/Videos"
KDENLIVE_MCP_ALLOWED_PROJECT_DIRS = "/home/abrahamc/Videos:/data/PROYECTOS/kdenlive-mcp/examples/recon"
KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS = "/home/abrahamc/Videos"
KDENLIVE_MCP_FLATPAK_ID = "org.kde.kdenlive"
KDENLIVE_MCP_LOG_FILE = "/data/PROYECTOS/kdenlive-mcp/logs/kdenlive-mcp.log"
```

A copy is available at:

```text
examples/codex_mcp_config.toml
```

The generic client-agnostic example is `examples/mcp_client_config.toml`.

Adjust the allowlists before use. The server should only receive directories
where the agent is allowed to read media or write generated artifacts.

## Validate The Local Setup

Default deterministic checks:

```bash
scripts/dev_check.sh
```

Include the fixture workflow check:

```bash
KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW=1 scripts/dev_check.sh
```

Run the 20-pass fixture reliability check:

```bash
KDENLIVE_MCP_RUN_RELIABILITY=1 scripts/dev_check.sh
```

Validate a generated project with Flatpak `melt`:

```bash
KDENLIVE_MCP_RUN_MLT_CHECK=1 \
KDENLIVE_MCP_MLT_PROJECT=/path/to/generated.kdenlive \
scripts/dev_check.sh
```

The MLT check may require running outside restrictive Codex sandboxes because
Flatpak can fail to allocate an instance inside the tool sandbox.

Run the real STDIO smoke test (starts the server as a subprocess and executes
`initialize` + `tools/list` over the real `Content-Length` framing):

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
