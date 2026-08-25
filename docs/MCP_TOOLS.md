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

### plan_silence_removal

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "threshold_db": -35,
  "minimum_duration": 0.8,
  "padding_before": 0.15,
  "padding_after": 0.15
}
```

Performs a dry-run cut plan from detected silence intervals:

```json
{
  "success": true,
  "dry_run": true,
  "cut_count": 17,
  "original_duration": 94.2,
  "removed_duration": 31.4,
  "resulting_duration": 62.8,
  "cuts": [
    {
      "cut_id": "silence_cut_001",
      "start": 12.55,
      "end": 15.65,
      "duration": 3.1
    }
  ]
}
```

The tool preserves padding around each detected silent range by cutting from
`silence_start + padding_before` to `silence_end - padding_after`. It does not
modify media or projects.

## Analysis Tools

Analysis tools enforce media and output allowlists. They create derived visual
artifacts only and never modify the original media.

### extract_frames

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "output_directory": "/home/abrahamc/Videos/vlog/frames",
  "every_seconds": 1.0,
  "max_frames": 12,
  "prefix": "clip"
}
```

Extracts periodic JPEG frames:

```text
clip_0001.jpg
clip_0002.jpg
clip_0003.jpg
```

The tool refuses to run when files with the selected prefix already exist in
the output directory.

### generate_contact_sheet

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "output": "/home/abrahamc/Videos/vlog/contact.jpg",
  "every_seconds": 1.0,
  "columns": 3,
  "rows": 3,
  "thumb_width": 320
}
```

Generates a single contact sheet image using FFmpeg `tile`. Existing output
files are not overwritten.

### detect_black_frames

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "minimum_duration": 0.5,
  "picture_black_ratio": 0.98,
  "pixel_black_threshold": 0.1
}
```

Runs FFmpeg `blackdetect` and returns black intervals:

```json
{
  "success": true,
  "operation": "detect_black_frames",
  "black_interval_count": 2,
  "black_intervals": [
    {
      "start": 0.0,
      "end": 1.0,
      "duration": 1.0
    }
  ]
}
```

This is read-only analysis. It helps detect black screens, accidental lens
covers, or unusable sections before building a timeline.

### detect_scene_changes

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "threshold": 0.35
}
```

Runs FFmpeg scene-score selection and returns timestamps:

```json
{
  "success": true,
  "operation": "detect_scene_changes",
  "scene_change_count": 2,
  "scene_changes": [
    {"time": 1.0},
    {"time": 2.0}
  ]
}
```

This is read-only analysis. Lower thresholds detect more cuts; higher
thresholds detect only stronger visual changes.

### detect_freeze_frames

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "noise_db": -60,
  "minimum_duration": 0.5
}
```

Runs FFmpeg `freezedetect` and returns frozen intervals:

```json
{
  "success": true,
  "operation": "detect_freeze_frames",
  "freeze_interval_count": 1,
  "freeze_intervals": [
    {
      "start": 0.0,
      "end": 2.0,
      "duration": 2.0
    }
  ]
}
```

If FFmpeg reports a freeze that continues to the end of the file without a
`freeze_end` event, the tool closes the interval using the media duration from
`ffprobe`.

### analyze_media

Input:

```json
{
  "media": "/home/abrahamc/Videos/vlog/clip.mp4",
  "include_silence": true,
  "include_black": true,
  "include_freeze": true,
  "include_scenes": true,
  "silence_threshold_db": -35,
  "silence_minimum_duration": 0.8,
  "black_minimum_duration": 0.5,
  "freeze_minimum_duration": 0.5,
  "scene_threshold": 0.35
}
```

Runs selected read-only analyses and returns compact subresults without the full
FFmpeg logs:

```json
{
  "success": true,
  "operation": "analyze_media",
  "summary": {
    "has_audio": true,
    "has_video": true,
    "duration_seconds": 3.0,
    "failure_count": 0
  },
  "analyses": {
    "silence": {
      "success": true,
      "silence_count": 0
    },
    "black": {
      "success": true,
      "black_interval_count": 0
    }
  }
}
```

Audio-only files skip visual analyses with an explicit `skipped` result.

### analyze_media_folder

Input:

```json
{
  "folder": "/home/abrahamc/Videos/vlog",
  "recursive": true,
  "max_files": 25,
  "include_silence": true,
  "include_black": true,
  "include_freeze": false,
  "include_scenes": true
}
```

Scans an allowed media folder without probing first, then runs `analyze_media`
for at most `max_files` files. `max_files` must be between 1 and 500.
`include_freeze` defaults to false for folder batches because freeze detection
can be comparatively expensive.

Output:

```json
{
  "success": true,
  "operation": "analyze_media_folder",
  "total_media_count": 27,
  "analyzed_count": 25,
  "skipped_count": 2,
  "failure_count": 0,
  "results": []
}
```

The tool is read-only. It does not create thumbnails, extracted frames, project
files, proxies, or edited media.

## Rough Cut Tools

### plan_rough_cut

Input:

```json
{
  "folder": "/home/abrahamc/Videos/vlog",
  "target_duration": 60,
  "recursive": true,
  "max_files": 25,
  "remove_silence": true,
  "silence_threshold_db": -35,
  "silence_minimum_duration": 0.8,
  "padding_before": 0.15,
  "padding_after": 0.15,
  "min_segment_duration": 0.25
}
```

Builds a read-only rough-cut plan from allowed media. The first implementation
selects clips in deterministic file order, optionally removes detected silence,
and trims the final segment to the requested target duration.

Output:

```json
{
  "success": true,
  "operation": "plan_rough_cut",
  "dry_run": true,
  "target_duration": 60.0,
  "planned_duration": 60.0,
  "selected_segment_count": 12,
  "segments": [
    {
      "segment_id": "rough_001",
      "media_id": "media_f293a81f",
      "source_in": 0.0,
      "source_out": 4.2,
      "timeline_in": 0.0,
      "timeline_out": 4.2,
      "reason": "sequential_selection"
    }
  ]
}
```

This tool does not create or modify Kdenlive projects. It produces the segment
plan that a later timeline writer can convert into `.kdenlive` entries after
the XML adapter is ready.

### save_rough_cut_plan

Input:

```json
{
  "plan": {
    "success": true,
    "operation": "plan_rough_cut",
    "dry_run": true,
    "segments": []
  },
  "output_directory": "/home/abrahamc/Videos/vlog",
  "name": "rough_cut_plan",
  "overwrite": false
}
```

Persists a successful dry-run rough-cut plan to:

```text
rough_cut_plan.rough-cut-plan.json
```

The persisted document includes:

```json
{
  "kind": "kdenlive_mcp_rough_cut_plan",
  "schema_version": 1,
  "created_at": "2026-08-25T00:00:00+00:00",
  "plan": {}
}
```

The tool writes only inside allowed output directories and refuses to overwrite
existing files unless `overwrite=true`.

### inspect_rough_cut_plan

Input:

```json
{
  "plan_file": "/home/abrahamc/Videos/vlog/rough_cut_plan.rough-cut-plan.json"
}
```

Loads and validates a persisted rough-cut plan document.

### create_rough_cut_plan_file

Input:

```json
{
  "folder": "/home/abrahamc/Videos/vlog",
  "output_directory": "/home/abrahamc/Videos/vlog",
  "name": "rough_cut_plan",
  "target_duration": 60,
  "remove_silence": true
}
```

Runs `plan_rough_cut` and immediately persists the successful result.

## Timeline Tools

These tools operate on the MCP-owned timeline JSON format, not on `.kdenlive`
XML. The format is intentionally simple: tracks, clips, stable IDs, media
references, source ranges, and timeline ranges.

### create_timeline_from_rough_cut_plan

Input:

```json
{
  "plan_file": "/home/abrahamc/Videos/vlog/rough_cut_plan.rough-cut-plan.json",
  "fps": 30,
  "width": 1080,
  "height": 1920
}
```

Output:

```json
{
  "success": true,
  "operation": "create_timeline_from_rough_cut_plan",
  "summary": {
    "track_count": 2,
    "clip_count": 24,
    "duration": 60.0,
    "fps": 30.0,
    "width": 1080,
    "height": 1920
  },
  "timeline": {
    "kind": "kdenlive_mcp_timeline",
    "schema_version": 1,
    "tracks": [],
    "clips": []
  }
}
```

The first implementation creates one video track and one linked audio track.
Each rough-cut segment becomes a video clip and an audio clip with matching
source/timeline ranges.

### save_timeline

Input:

```json
{
  "timeline": {
    "kind": "kdenlive_mcp_timeline",
    "tracks": [],
    "clips": []
  },
  "output_directory": "/home/abrahamc/Videos/vlog",
  "name": "timeline",
  "overwrite": false
}
```

Writes `<name>.timeline.json` in an allowed output directory and validates the
timeline before saving.

### inspect_timeline

Input:

```json
{
  "timeline_file": "/home/abrahamc/Videos/vlog/timeline.timeline.json"
}
```

Loads and validates a persisted MCP timeline document.

### validate_timeline

Input:

```json
{
  "timeline_file": "/home/abrahamc/Videos/vlog/timeline.timeline.json",
  "check_media_exists": true,
  "duration_tolerance": 0.001
}
```

Checks the timeline for:

```text
TIMELINE_OVERLAP
DURATION_MISMATCH
LINKED_CLIP_MISMATCH
MEDIA_OFFLINE
PERMISSION_DENIED media references
```

Output:

```json
{
  "success": true,
  "operation": "validate_timeline",
  "valid": false,
  "issue_count": 1,
  "issues": [
    {
      "code": "TIMELINE_OVERLAP",
      "track_id": "track_v1",
      "clip_id": "clip_002_v",
      "previous_clip_id": "clip_001_v"
    }
  ]
}
```

### export_timeline_to_mlt_xml

Input:

```json
{
  "timeline_file": "/home/abrahamc/Videos/vlog/timeline.timeline.json",
  "output_directory": "/home/abrahamc/Videos/vlog",
  "name": "timeline_draft",
  "overwrite": false,
  "check_media_exists": true
}
```

Exports a validated MCP timeline to:

```text
timeline_draft.mlt.xml
```

This is an experimental MLT XML draft, not a `.kdenlive` project. It contains:

```text
mlt
profile
producer elements for media references
playlist elements for MCP tracks
blank entries for timeline gaps
tractor main_tractor
```

The tool refuses to export invalid timelines and returns `kdenlive_project:
false` in the result.

### export_timeline_to_kdenlive_template

Input:

```json
{
  "timeline_file": "/home/abrahamc/Videos/vlog/timeline.timeline.json",
  "template_project": "/home/abrahamc/Videos/templates/manual_empty_vertical.kdenlive",
  "output_directory": "/home/abrahamc/Videos/vlog",
  "name": "vlog_ai_001",
  "overwrite": false,
  "check_media_exists": true
}
```

Creates a derived `.kdenlive` draft by copying a real Kdenlive template and
filling the observed audio/video playlists with clips from the MCP timeline.

Current constraints:

```text
template must contain main_bin, playlist0, playlist6, tractor4
one audio track target: playlist0
one video track target: playlist6
no effects, transitions, subtitles, proxies, or track renames
unknown template XML is preserved where possible
```

The tool validates the output with `KdenliveProjectAdapter.inspect()` and
returns a summary with bin media count, sequence count, active sequence, and
timeline clip count.

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
