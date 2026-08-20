# kdenlive-mcp

Local MCP server for safe Kdenlive automation experiments.

The project goal is not to replace Kdenlive or modify Kdenlive source code. The
goal is to expose safe tools that let an AI agent inspect media, reason about
editing operations, and eventually produce Kdenlive projects that remain
editable in Kdenlive.

Current status: reconnaissance, Phase 1 MCP skeleton, Phase 2 media tools, an
intermediate MCP manifest layer, and real Kdenlive 26.04.3 reference fixtures.
The server exposes environment/version tools, non-destructive media
inspection/derivation tools, read-only Kdenlive project inspection/validation,
and non-destructive project backup/clone tools. It does not mutate `.kdenlive`
XML yet.

## Install For Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

The current environment already has Python 3.13, Pydantic, pytest, FFmpeg,
ffprobe, and Kdenlive Flatpak available. The official `mcp` Python package was
not installed during reconnaissance, so this repository currently includes a
small compatible JSON-RPC STDIO server for Phase 1.

## Run

```bash
python3 src/kdenlive_mcp/server.py
```

For media tools, configure allowlists before launching the server:

```bash
export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS=/home/abrahamc/Videos:/tmp
```

Codex MCP configuration example:

```toml
[mcp_servers.kdenlive]
command = "python3"
args = ["/data/PROYECTOS/kdenlive-mcp/src/kdenlive_mcp/server.py"]
```

## Current Tools

```text
health_check
get_environment
get_kdenlive_version
get_ffmpeg_version
get_ffprobe_version
get_mlt_version
scan_media
list_media
get_media_info
validate_media
generate_thumbnail
extract_audio
detect_silence
plan_silence_removal
extract_frames
generate_contact_sheet
detect_black_frames
create_manifest
inspect_manifest
validate_manifest
scan_media_to_manifest
inspect_project
validate_project
backup_project
clone_project
list_project_versions
restore_project_version
get_project_lock
lock_project
unlock_project
prepare_working_project
```

All tools return structured JSON text through MCP `tools/call`.

## Tests

```bash
python3 -m pytest
```

## Documentation

```text
docs/ENVIRONMENT.md
docs/ARCHITECTURE.md
docs/KDENLIVE_PROJECT_FORMAT.md
docs/MCP_TOOLS.md
docs/SECURITY.md
```

## Known Limitation

Do not implement `.kdenlive` writing until the read-only adapter can parse the
captured fixtures and additional trim/gap samples have been studied. Plain MLT
XML is not enough to define a safe Kdenlive project writer.
