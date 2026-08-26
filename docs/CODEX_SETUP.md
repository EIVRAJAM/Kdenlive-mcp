# Codex MCP Setup

This project exposes a local MCP server over STDIO.

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

Validate a generated project with Flatpak `melt`:

```bash
KDENLIVE_MCP_RUN_MLT_CHECK=1 \
KDENLIVE_MCP_MLT_PROJECT=/path/to/generated.kdenlive \
scripts/dev_check.sh
```

The MLT check may require running outside restrictive Codex sandboxes because
Flatpak can fail to allocate an instance inside the tool sandbox.
