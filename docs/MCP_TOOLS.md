# MCP Tools

Current phase: Phase 1 STDIO server.

The server is intentionally narrow. It exposes environment and version
inspection only; it does not create or modify Kdenlive projects yet.

## Codex Configuration

```toml
[mcp_servers.kdenlive]
command = "python3"
args = ["/data/PROYECTOS/kdenlive-mcp/src/kdenlive_mcp/server.py"]
```

## Transport

The server speaks JSON-RPC 2.0 over STDIO using MCP-style `Content-Length`
framing.

Supported methods:

```text
initialize
ping
tools/list
tools/call
resources/list
prompts/list
notifications/*
```

`resources/list` and `prompts/list` currently return empty lists.

## Tools

### health_check

Input:

```json
{}
```

Returns:

```json
{
  "success": true,
  "service": "kdenlive-mcp",
  "version": "0.1.0",
  "status": "ok",
  "capabilities": [
    "environment_detection",
    "version_detection",
    "mcp_stdio_jsonrpc"
  ]
}
```

### get_environment

Input:

```json
{}
```

Returns Python, platform, binary availability, current working directory, and
configured allowlist directories.

### get_kdenlive_version

Input:

```json
{}
```

Attempts:

```bash
flatpak run --command=kdenlive org.kde.kdenlive --version
```

If Flatpak execution is unavailable inside the command sandbox, falls back to:

```bash
flatpak info org.kde.kdenlive
```

Falls back to:

```bash
kdenlive --version
```

### get_ffmpeg_version

Input:

```json
{}
```

Runs:

```bash
ffmpeg -version
```

### get_ffprobe_version

Input:

```json
{}
```

Runs:

```bash
ffprobe -version
```

### get_mlt_version

Input:

```json
{}
```

Attempts host MLT first:

```bash
melt -version
```

Falls back to Kdenlive Flatpak MLT:

```bash
flatpak run --command=melt org.kde.kdenlive -version
```

If Flatpak execution is unavailable inside the command sandbox, it attempts to
infer the installed MLT version from the Flatpak installation location:

```bash
flatpak info --show-location org.kde.kdenlive
```

## Sandbox Note

Inside the Codex command sandbox, `flatpak run` may fail with:

```text
error: Unable to allocate instance id
```

This was observed during reconnaissance. The server now treats this as
`FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX` and uses read-only Flatpak metadata
fallbacks where possible:

```text
get_kdenlive_version -> flatpak info
get_mlt_version -> Flatpak installation scan for libmlt-7.so.*
```

The same Flatpak execution commands work when allowed to run outside the
sandbox. Render and project-load operations will still require a process context
where `flatpak run` can execute.

## Verification Commands

```bash
python3 -m pytest
python3 -m compileall src tests
python3 src/kdenlive_mcp/server.py
```
