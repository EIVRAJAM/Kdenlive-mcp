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
    -> Audio analysis tools
    -> Video analysis tools
    -> MCP project manifest
    -> Kdenlive project inspector/validator
    -> Template-based .kdenlive draft writer
    -> Project backup/clone service
    -> Project lock service
      -> FFmpeg / ffprobe
      -> Kdenlive XML
```

Expanded write/editing scope:

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
src/kdenlive_mcp/tools/audio_tools.py
src/kdenlive_mcp/tools/analysis_tools.py
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

`kdenlive_xml.py` parses Kdenlive-generated `.kdenlive` files into structured
project summaries. It also owns the first limited writer path, which copies a
real empty Kdenlive template and fills one observed audio/video playlist pair.

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
src/kdenlive_mcp/services/backup_service.py
src/kdenlive_mcp/services/lock_service.py
```

Services coordinate domain models, security validation, and tool/adapters.

Current manifest services:

```text
create manifest
inspect manifest
validate manifest
scan media into manifest
backup project
clone project
list project versions
restore project version
lock project
unlock project
get project lock
prepare working project
```

`backup_service.py` implements copy-on-write preparation. It validates the
source project, creates timestamped backups, creates `_ai_001` style working
copies, validates clones after copying, and lists related working copies and
backups for history/undo planning. Restores are also copy-on-write: selected
versions are copied into new `_restored_001` style files rather than overwriting
active projects. It does not modify XML.

`lock_service.py` implements JSON lock files for project-level concurrency. It
uses owner-scoped locks, refuses conflicting owners, supports forced unlock, and
keeps lock files in allowed output directories.

`project_workflow_service.py` composes clone, backup, and lock into the
recommended pre-edit flow: create a working copy, preserve a backup, then lock
the working copy for the current owner.

The operator-level undo flow is documented in `docs/UNDO_VERSIONING.md`. Undo
is implemented as copy-on-write restore: a selected valid version is copied into
a new `_restored_001` style project, while the current project remains
unchanged and is backed up first by default.

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

The adapter owns parsing and the limited template writer:

```text
XML parsing
XML serialization
Kdenlive-specific property names
producer / playlist / tractor mapping
round-trip preservation of unknown properties
validation of references and timings
```

The rest of the system should use domain objects and services, not raw XML.

## Kdenlive Writing Scope

Real Kdenlive 26.04.3 reference files have been captured:

```text
manual_empty_vertical.kdenlive
manual_bin_only.kdenlive
manual_two_clips_timeline.kdenlive
manual_trim_marker.kdenlive
```

They confirm the basic structure of `main_bin`, sequences, tracks, media
chains, timeline entries, groups, guides, and markers.

The first writer path is deliberately limited: it copies
`manual_empty_vertical.kdenlive`, detects one editable audio/video playlist pair
from the active sequence, and fills it from a generated MCP timeline. Full
`.kdenlive` editing remains blocked until additional samples confirm trimmed
clips, gaps, multi-track edits, and round-trip preservation tests.

## Testing Strategy

Current tests cover:

```text
MCP framing and tool calls
environment tools
Flatpak sandbox fallbacks
media scanning and ffprobe metadata
thumbnail/audio derivation
FFmpeg silence detection
dry-run silence removal planning
visual frame extraction and contact sheets
black frame interval detection
scene change timestamp detection
freeze interval detection
aggregate media analysis
batch folder media analysis
dry-run rough cut planning
rough cut plan JSON persistence
MCP timeline JSON creation and validation
timeline overlap, duration, link, and media-reference validation
experimental MCP timeline to MLT XML draft export
template-based .kdenlive draft export
end-to-end vlog rough-cut project workflow
path traversal rejection
manifest creation, inspection, validation, and media scan persistence
Kdenlive XML fixture parsing
read-only Kdenlive project validation
non-destructive project backup and clone generation
project lock lifecycle
```

Tests use small synthetic media under:

```text
examples/recon/
```

Future adapter tests should use only small `.kdenlive` fixtures generated by the
installed Kdenlive version.
