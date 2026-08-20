# Architecture

This project builds a local MCP layer that lets an AI agent inspect media and
prepare editing state for Kdenlive without replacing Kdenlive or modifying
Kdenlive source code.

Current implemented scope:

```text
Codex / AI agent
  -> MCP STDIO server
    -> Environment tools
    -> Media tools
    -> MCP project manifest
    -> Read-only Kdenlive project inspector
      -> FFmpeg / ffprobe
      -> Kdenlive XML
```

Planned write/editing scope:

```text
Codex / AI agent
  -> MCP STDIO server
    -> Services
      -> Domain model
        -> KdenliveProjectAdapter
          -> Kdenlive XML / MLT
```

## Design Principles

The system is non-destructive by default.

Original media files are never modified. Derived outputs such as thumbnails and
extracted WAV files must be written to allowed output directories and must not
overwrite existing files.

The domain layer must not manipulate Kdenlive XML directly. Kdenlive-specific
format behavior belongs behind `KdenliveProjectAdapter`.

The current manifest format is MCP-owned JSON. It is not a `.kdenlive` file and
is not meant to be opened by Kdenlive.

## Current Layers

### MCP Server

Location:

```text
src/kdenlive_mcp/server.py
```

Responsibilities:

```text
JSON-RPC 2.0 / MCP-style STDIO framing
initialize / ping
tools/list
tools/call
resources/list
prompts/list
structured tool responses
```

The server currently uses a small compatible JSON-RPC implementation because
the official Python `mcp` package was not installed in the initial environment.
The public tool boundary is intentionally simple so it can later be migrated to
the official SDK.

### Tools

Locations:

```text
src/kdenlive_mcp/tools/environment_tools.py
src/kdenlive_mcp/tools/media_tools.py
src/kdenlive_mcp/tools/manifest_tools.py
src/kdenlive_mcp/tools/project_tools.py
```

Tool modules expose dictionaries with:

```text
name
description
inputSchema
handler
```

The server merges those registries for MCP discovery.

### Adapters

Locations:

```text
src/kdenlive_mcp/adapters/commands.py
src/kdenlive_mcp/adapters/ffmpeg.py
src/kdenlive_mcp/adapters/ffprobe.py
src/kdenlive_mcp/adapters/kdenlive_xml.py
```

Adapters own subprocess interaction. Commands must use:

```python
subprocess.run([...], shell=False)
```

No shell command strings should be assembled from user input.

`kdenlive_xml.py` is currently read-only. It parses Kdenlive-generated
`.kdenlive` files into structured project summaries and does not serialize or
modify XML yet.

### Security

Location:

```text
src/kdenlive_mcp/security.py
```

The security layer resolves paths and enforces allowlists before tools read from
or write to the filesystem.

Current allowlist categories:

```text
allowed_media_directories
allowed_project_directories
allowed_output_directories
```

### Domain

Location:

```text
src/kdenlive_mcp/domain/manifest.py
```

Current domain model:

```text
ProjectManifest
ManifestMediaItem
```

The manifest persists media inventory and stable media IDs before Kdenlive
project writing exists.

### Services

Location:

```text
src/kdenlive_mcp/services/manifest_service.py
```

Services coordinate domain models, security validation, and tool/adapters.

Current manifest services:

```text
create manifest
inspect manifest
validate manifest
scan media into manifest
```

## Data Flow: Media Scan To Manifest

```text
Codex
  -> tools/call scan_media_to_manifest
    -> validate manifest path against output allowlist
    -> validate source folder against media allowlist
    -> scan_media
      -> ffprobe
    -> assign stable media IDs
    -> write *.kdenlive-mcp.json
```

## Stable IDs

Media IDs are derived from absolute media paths:

```text
media_<sha1-prefix>
```

This is stable for a given local path and avoids relying on timeline indices or
Kdenlive-generated IDs before the adapter exists.

Future adapter work may map:

```text
manifest media ID <-> Kdenlive producer/bin ID
```

## Kdenlive Adapter Boundary

Location:

```text
src/kdenlive_mcp/adapters/kdenlive_xml.py
```

The adapter owns read-only parsing now and should own writing later:

```text
XML parsing
XML serialization
Kdenlive-specific property names
producer / playlist / tractor mapping
round-trip preservation of unknown properties
validation of references and timings
```

The rest of the system should use domain objects and services, not raw XML.

## Required Before Kdenlive Writing

Real Kdenlive 26.04.3 reference files have been captured:

```text
manual_empty_vertical.kdenlive
manual_bin_only.kdenlive
manual_two_clips_timeline.kdenlive
manual_trim_marker.kdenlive
```

They confirm the basic structure of `main_bin`, sequences, tracks, media
chains, timeline entries, groups, guides, and markers. `.kdenlive` writing
remains intentionally blocked until additional samples confirm trimmed clips and
gaps, and until round-trip preservation tests exist.

## Testing Strategy

Current tests cover:

```text
MCP framing and tool calls
environment tools
Flatpak sandbox fallbacks
media scanning and ffprobe metadata
thumbnail/audio derivation
path traversal rejection
manifest creation, inspection, validation, and media scan persistence
Kdenlive XML fixture parsing
```

Tests use small synthetic media under:

```text
examples/recon/
```

Future adapter tests should use only small `.kdenlive` fixtures generated by the
installed Kdenlive version.
