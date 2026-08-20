# MCP Tools

Current phase: intermediate manifest layer plus read-only Kdenlive project
inspection.

The server is intentionally narrow. It exposes environment/version inspection
and non-destructive media/manifest/project inspection tools only; it does not
create or modify Kdenlive projects yet.

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

Project tools enforce `KDENLIVE_MCP_ALLOWED_PROJECT_DIRS`. They are read-only in
the current phase.

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

## Verification Commands

```bash
python3 -m pytest
python3 -m compileall src tests
python3 src/kdenlive_mcp/server.py
```
