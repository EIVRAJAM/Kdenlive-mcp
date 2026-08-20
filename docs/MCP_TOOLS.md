# MCP Tools

Current phase: intermediate manifest layer, read-only Kdenlive project
inspection, non-destructive project backup/clone operations, and project locks.

The server is intentionally narrow. It exposes environment/version inspection
and non-destructive media/manifest/project tools only. It can copy `.kdenlive`
files, but it does not mutate Kdenlive XML yet.

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

## Media Tools

Media tools enforce path allowlists. Configure them before launching the MCP
server:

```bash
export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS=/home/abrahamc/Videos:/tmp
```

Paths outside these roots, including traversal attempts such as `../outside`,
return:

```json
{
  "success": false,
  "error": "PERMISSION_DENIED"
}
```

Supported extensions currently include:

```text
.3gp .aac .aiff .flac .m4a .mkv .mov .mp3 .mp4 .ogg .wav .webm
```

### scan_media

Input:

```json
{
  "folder": "/home/abrahamc/Videos/vlog",
  "recursive": true,
  "probe": true
}
```

Finds supported media files. When `probe` is true, runs `ffprobe` on each file
and returns duration, format, bitrate, video stream details, audio stream
details, and metadata.

### list_media

Input:

```json
{
  "folder": "/home/abrahamc/Videos/vlog",
  "recursive": true
}
```

Lists supported media files without running `ffprobe`.

### get_media_info

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4"
}
```

Returns structured `ffprobe` metadata for one file.

### validate_media

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4"
}
```

Checks that the file exists, has a supported extension, can be probed, and has
at least one audio or video stream.

### generate_thumbnail

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "output": "/home/abrahamc/Videos/vlog/thumbs/clip.jpg",
  "timestamp": 1.0
}
```

Generates a derived image with FFmpeg. The original media file is not modified.
The tool refuses to overwrite an existing output file and rejects an output path
that resolves to the input media file.

### extract_audio

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "output": "/home/abrahamc/Videos/vlog/audio/clip.wav"
}
```

Extracts a derived WAV file with FFmpeg. The original media file is not
modified. The tool refuses to overwrite an existing output file and rejects an
output path that resolves to the input media file.

## Audio Tools

Audio tools enforce `KDENLIVE_MCP_ALLOWED_MEDIA_DIRS` and do not modify the
input media.

### detect_silence

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "threshold_db": -35,
  "minimum_duration": 0.8
}
```

Runs FFmpeg `silencedetect` and returns structured intervals:

```json
{
  "success": true,
  "operation": "detect_silence",
  "silence_count": 1,
  "silences": [
    {
      "start": 12.4,
      "end": 15.8,
      "duration": 3.4
    }
  ]
}
```

This is analysis only. It does not remove timeline sections; future timeline
tools will consume these intervals with explicit padding and dry-run support.

## Manifest Tools

The manifest layer is an intermediate MCP-owned JSON format. It is not a
`.kdenlive` project and is not intended to be opened by Kdenlive. It gives the
agent a safe place to persist media scans, stable media IDs, notes, and future
planning metadata before Kdenlive project writing is implemented.

Manifest files use this filename convention:

```text
<name>.kdenlive-mcp.json
```

They must be created in an allowed output directory.

### create_manifest

Input:

```json
{
  "name": "Vlog Santa Marta",
  "output_directory": "/home/abrahamc/Videos/VlogSantaMarta",
  "description": "Initial media inventory",
  "overwrite": false
}
```

Creates a JSON manifest with schema/version metadata. Existing files are not
overwritten unless `overwrite` is true.

### inspect_manifest

Input:

```json
{
  "manifest": "/home/abrahamc/Videos/VlogSantaMarta/Vlog_Santa_Marta.kdenlive-mcp.json"
}
```

Loads and returns the manifest contents.

### validate_manifest

Input:

```json
{
  "manifest": "/home/abrahamc/Videos/VlogSantaMarta/Vlog_Santa_Marta.kdenlive-mcp.json"
}
```

Validates manifest structure, duplicate media IDs, and referenced media file
existence.

### scan_media_to_manifest

Input:

```json
{
  "manifest": "/home/abrahamc/Videos/VlogSantaMarta/Vlog_Santa_Marta.kdenlive-mcp.json",
  "folder": "/home/abrahamc/Videos/VlogSantaMarta",
  "recursive": true,
  "replace": true
}
```

Runs `scan_media` and stores the resulting media inventory in the manifest. Each
media item gets a stable ID derived from its absolute path, for example:

```text
media_4f89c2a613bf
```

## Project Tools

Project tools enforce `KDENLIVE_MCP_ALLOWED_PROJECT_DIRS` for source projects.
Tools that create files also enforce `KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS`.

### inspect_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive"
}
```

Reads one `.kdenlive` file and returns a structured summary:

```json
{
  "success": true,
  "operation": "inspect_project",
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive",
  "data": {
    "profile": {
      "width": 1080,
      "height": 1920,
      "frame_rate_num": 30,
      "frame_rate_den": 1
    },
    "document": {
      "kdenlive_version": "26.04.3",
      "profile": "vertical_hd_30"
    },
    "bin": {
      "media_count": 2,
      "media": []
    },
    "sequences": [],
    "validation": {
      "well_formed_xml": true,
      "missing_media_count": 0
    }
  }
}
```

The parser currently extracts:

```text
profile
document properties
main_bin media entries
active sequence
track branches
timeline clips
guides
markers
basic missing-media validation
```

It does not write, normalize, or save XML.

### validate_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive",
  "check_mlt": false,
  "timeout": 20
}
```

Performs read-only validation:

```text
XML parse
Kdenlive project shape
media reference existence
optional MLT load through Flatpak melt
```

When `check_mlt` is true, the tool runs:

```bash
flatpak run --command=melt org.kde.kdenlive \
  /path/to/project.kdenlive \
  -consumer null terminate_on_pause=1
```

If Flatpak execution is blocked by the Codex sandbox, the MLT check is reported
as unavailable:

```json
{
  "checked": true,
  "valid": null,
  "status": "unavailable",
  "error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
}
```

That specific sandbox condition does not mark the project invalid; static XML
and media-reference checks still determine the result.

### backup_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog.kdenlive",
  "backup_directory": "/home/abrahamc/Videos/Vlog/.backups",
  "label": "before_ai_edit"
}
```

Creates a timestamped copy after validating the source project:

```text
.backups/vlog_before_ai_edit_2026-08-20_143022_001.kdenlive
```

The tool refuses paths outside allowlists and never overwrites an existing
backup.

### clone_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog.kdenlive",
  "output_directory": "/home/abrahamc/Videos/Vlog",
  "suffix": "_ai",
  "create_backup": true
}
```

Creates the next available AI working copy:

```text
vlog_ai_001.kdenlive
vlog_ai_002.kdenlive
vlog_ai_003.kdenlive
```

When `create_backup` is true, it also creates a backup under:

```text
<output_directory>/.backups/
```

The clone is validated after copying. Current clone behavior copies the project
file as-is; it does not rewrite the Kdenlive XML `root` attribute or media
paths.

### list_project_versions

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog.kdenlive",
  "project_directory": "/home/abrahamc/Videos/Vlog",
  "backup_directory": "/home/abrahamc/Videos/Vlog/.backups"
}
```

Lists related project files:

```text
original project, when present in the scanned directory
working copies such as vlog_ai_001.kdenlive
timestamped backups
other related .kdenlive files sharing the same base stem
```

This is read-only and intended for history/undo planning. It does not restore
or overwrite any project.

### restore_project_version

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog.kdenlive",
  "version": "/home/abrahamc/Videos/Vlog/vlog_ai_002.kdenlive",
  "output_directory": "/home/abrahamc/Videos/Vlog",
  "suffix": "_restored",
  "create_backup": true,
  "backup_directory": "/home/abrahamc/Videos/Vlog/.backups"
}
```

Creates a new restored copy, for example:

```text
vlog_restored_001.kdenlive
```

It validates the current project and selected version, optionally backs up the
current project, copies the selected version to the new restored file, and
validates the restored copy. It never overwrites the current project or the
selected version.

### get_project_lock

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive",
  "lock_directory": "/home/abrahamc/Videos/Vlog/.locks"
}
```

Returns whether a lock exists and, when present, its owner and metadata.

### lock_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive",
  "owner": "codex",
  "lock_directory": "/home/abrahamc/Videos/Vlog/.locks",
  "stale_after_seconds": 86400
}
```

Creates an owner-scoped JSON lock. Calling it again with the same owner is
idempotent. Calling it with a different owner returns:

```json
{
  "success": false,
  "error": "PROJECT_LOCKED"
}
```

### unlock_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog_ai_001.kdenlive",
  "owner": "codex",
  "lock_directory": "/home/abrahamc/Videos/Vlog/.locks",
  "force": false
}
```

Unlocks only when the owner matches unless `force` is true. Lock directories
must be inside `KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS`.

### prepare_working_project

Input:

```json
{
  "project": "/home/abrahamc/Videos/Vlog/vlog.kdenlive",
  "output_directory": "/home/abrahamc/Videos/Vlog",
  "suffix": "_ai",
  "owner": "codex",
  "create_backup": true,
  "backup_directory": "/home/abrahamc/Videos/Vlog/.backups",
  "lock_directory": "/home/abrahamc/Videos/Vlog/.locks"
}
```

This is the recommended pre-edit workflow. It performs:

```text
validate source project
create backup
create next working copy, e.g. vlog_ai_001.kdenlive
validate working copy
lock working copy
```

The output directory must be allowed both as an output directory and as a
project directory, because the resulting working copy becomes the next project
to inspect or edit.

## Verification Commands

```bash
python3 -m pytest
python3 -m compileall src tests
python3 src/kdenlive_mcp/server.py
```
