# Persisted JSON Schemas

This document describes the versioned JSON files persisted by `kdenlive-mcp`.
These are MCP-owned formats. They are not Kdenlive project files.

## Compatibility Rules

```text
schema_version is required
kind is required
new optional fields may be added in the same schema version
required fields must not be removed without a new schema version
field units must not change within the same schema version
agents should ignore unknown fields
writers should preserve known fields and may drop unknown fields only when documented
```

Time values in these schemas are seconds as floating point numbers. Frame and
timecode conversion belongs at adapter boundaries only.

Paths are stored as absolute normalized local paths after allowlist validation.

## Schema Migration Policy

This policy applies to every JSON file persisted by the MCP: rough-cut plans
(`*.rough-cut-plan.json`), timeline documents (`*.timeline.json`), and project
manifests (`*.kdenlive-mcp.json`).

### Version Requirement

```text
schema_version is required in every persisted JSON file
kind is required for rough-cut plans and timeline documents
readers must reject higher or unsupported schema versions with a structured error
```

### Compatible Changes Allowed In v1

```text
adding optional fields
adding optional values that are not required
expanding metadata without changing field semantics
```

### Incompatible Changes That Require v2

```text
changing time units
renaming or removing required fields
changing the meaning of IDs
changing the structure of tracks/clips/segments
changing path semantics
```

### Agent Policy

```text
do not edit persisted JSON files manually except through the MCP tools
preserve kind and schema_version when a tool rewrites a persisted file
if a tool returns UNSUPPORTED_SCHEMA_VERSION, stop and request an explicit migration
```

### Future Migration Policy

```text
migrators must be explicit, never silent or automatic
migration must support dry_run
a backup must be created before writing a migration
round-trip tests must cover the document before and after migration
```

### Current Error Codes (v1)

```text
rough-cut plan with unsupported schema_version: INVALID_ROUGH_CUT_PLAN
project manifest that fails validation: INVALID_MANIFEST
timeline with unsupported schema_version: no explicit check today (schema_version
is an int field and load_timeline_document accepts the value)

TODO(unify): introduce UNSUPPORTED_SCHEMA_VERSION as the single structured error
code for unsupported schema versions across rough-cut plan, timeline document and
project manifest.
```

### Persisted Kinds Covered

```text
kdenlive_mcp_rough_cut_plan  (rough-cut-plan.json, schema_version 1)
kdenlive_mcp_timeline        (timeline.json, schema_version 1)
kdenlive-mcp.json            (project manifest, schema_version "1.0")
```

## Rough-Cut Plan Document v1

Filename convention:

```text
<name>.rough-cut-plan.json
```

Top-level shape:

```json
{
  "kind": "kdenlive_mcp_rough_cut_plan",
  "schema_version": 1,
  "created_at": "2026-08-25T12:00:00+00:00",
  "plan": {}
}
```

Required fields:

```text
kind
schema_version
created_at
plan
```

The `plan` object is the successful output of `plan_rough_cut`.

### plan Object v1

Required fields:

```text
success
operation
dry_run
folder
recursive
target_duration
planned_duration
total_media_count
analyzed_media_count
selected_segment_count
skipped_media_count
failure_count
remove_silence
segments
skipped_media
failures
```

Required values:

```text
success: true
operation: plan_rough_cut
dry_run: true
```

Example:

```json
{
  "success": true,
  "operation": "plan_rough_cut",
  "dry_run": true,
  "folder": "/home/abrahamc/Videos/vlog",
  "recursive": true,
  "target_duration": 60.0,
  "planned_duration": 58.4,
  "total_media_count": 27,
  "analyzed_media_count": 25,
  "selected_segment_count": 14,
  "skipped_media_count": 0,
  "failure_count": 0,
  "remove_silence": true,
  "segments": [],
  "skipped_media": [],
  "failures": []
}
```

### Segment v1

Required fields:

```text
segment_id
media_id
media
source_in
source_out
duration
timeline_in
timeline_out
reason
```

Example:

```json
{
  "segment_id": "rough_001",
  "media_id": "media_a81f20cc",
  "media": "/home/abrahamc/Videos/vlog/GX010001.mp4",
  "source_in": 12.4,
  "source_out": 16.2,
  "duration": 3.8,
  "timeline_in": 0.0,
  "timeline_out": 3.8,
  "reason": "silence_removed"
}
```

Validation rules:

```text
source_in >= 0
source_out > source_in
duration == source_out - source_in within tolerance
timeline_in >= 0
timeline_out > timeline_in
timeline duration equals duration within tolerance
segment_id is stable inside the plan
media points to an allowed media path
```

## Timeline Document v1

Filename convention:

```text
<name>.timeline.json
```

Top-level shape:

```json
{
  "kind": "kdenlive_mcp_timeline",
  "schema_version": 1,
  "created_by": "kdenlive-mcp",
  "created_with_version": "0.1.0",
  "created_at": "2026-08-25T12:00:00+00:00",
  "source_plan_file": "/home/abrahamc/Videos/vlog/plan.rough-cut-plan.json",
  "source_plan_kind": "kdenlive_mcp_rough_cut_plan",
  "fps": 30.0,
  "width": 1080,
  "height": 1920,
  "tracks": [],
  "clips": [],
  "markers": []
}
```

Required fields:

```text
kind
schema_version
created_by
created_with_version
created_at
fps
width
height
tracks
clips
markers
```

Optional fields:

```text
source_plan_file
source_plan_kind
```

### Track v1

Required fields:

```text
id
type
name
locked
muted
```

Allowed `type` values:

```text
video
audio
```

Example:

```json
{
  "id": "track_v1",
  "type": "video",
  "name": "Video 1",
  "locked": false,
  "muted": false
}
```

### Clip v1

Required fields:

```text
id
track_id
media_id
media
source_in
source_out
timeline_in
timeline_out
speed
```

Optional fields:

```text
linked_clip_id
source_segment_id
reason
```

Example:

```json
{
  "id": "clip_001_v",
  "track_id": "track_v1",
  "media_id": "media_a81f20cc",
  "media": "/home/abrahamc/Videos/vlog/GX010001.mp4",
  "source_in": 12.4,
  "source_out": 16.2,
  "timeline_in": 0.0,
  "timeline_out": 3.8,
  "speed": 1.0,
  "linked_clip_id": "clip_001_a",
  "source_segment_id": "rough_001",
  "reason": "silence_removed"
}
```

Validation rules:

```text
source_in >= 0
source_out > source_in
timeline_in >= 0
timeline_out > timeline_in
speed > 0
track_id references an existing track
linked_clip_id references an existing clip when present
clip IDs are unique
clips on the same track must not overlap
linked audio/video clips must match media and timing
```

### Marker v1

Required fields:

```text
id
comment
position
duration
type
```

Example:

```json
{
  "id": "marker_001",
  "comment": "rough_001",
  "position": 0.0,
  "duration": 3.8,
  "type": 0
}
```

Validation rules:

```text
position >= 0
duration >= 0
comment is not empty
marker IDs are unique
```

## Kdenlive Adapter Mapping

Timeline v1 maps into `.kdenlive` drafts as follows:

```text
TimelineDocument.fps/width/height -> used for validation against template profile
TimelineTrack -> current writer chooses one detected audio/video pair from template
TimelineClip -> playlist entry and media chain references
TimelineMarker -> kdenlive:sequenceproperties.guides and kdenlive:markers
```

Kdenlive guide/marker `pos` and `duration` values are stored as frames. The MCP
timeline stores seconds and lets `KdenliveProjectAdapter` perform conversion.

## Future Schema Versions

Expected future additions:

```text
multiple editable tracks
clip groups
transitions
effects
subtitles
proxy references
render jobs
```

These must be added as optional fields in v1 where possible. If existing field
meaning changes, create schema_version 2 instead.
