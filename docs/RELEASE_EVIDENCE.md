# Release Evidence

This file records local validation evidence for production-readiness gates.

## 2026-08-25 Fixture Reliability Gate

Release target:

```text
production-local-agent-single-user
```

Validated commit:

```text
c3d418a
```

Command:

```bash
KDENLIVE_MCP_RUN_RELIABILITY=1 scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 118 passed in 17.91s
fixture reliability: passed
runs: 20
media_checksums_unchanged: true
overwrite_refusal_checked: true
timeline_clip_count sample: 4
marker_count sample: 2
guide_count sample: 2
```

Raw fixture reliability output:

```json
{
  "success": true,
  "operation": "fixture_reliability_check",
  "runs": 20,
  "media_checksums_unchanged": true,
  "overwrite_refusal_checked": true,
  "sample": {
    "iteration": 1,
    "project": "/tmp/kdenlive-mcp-reliability-li12hj5q/reliability_001.kdenlive",
    "timeline_clip_count": 4,
    "marker_count": 2,
    "guide_count": 2
  }
}
```

Decision:

```text
The 20-pass fixture workflow reliability gate is satisfied for commit c3d418a.
```

Remaining production-local-agent evidence:

```text
manual Kdenlive open verification for that generated project
```

## 2026-08-25 Real User Media Folder Validation

Release target:

```text
production-local-agent-single-user
```

Validated commit:

```text
4bdcd70
```

Machine date:

```text
2026-08-25T23:26:59-05:00
```

Environment:

```text
Kdenlive Flatpak: org.kde.kdenlive 26.04.3
FFmpeg: 7.1.4-0+deb13u1
MLT melt: 7.40.0
```

Media folder:

```text
/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones
```

Command shape:

```text
create_vlog_rough_cut_project(
  target_duration=8,
  recursive=False,
  max_files=2,
  remove_silence=False,
  overwrite=True,
  check_mlt=True
)
```

Generated project:

```text
/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones/kdenlive_mcp_real_validation.kdenlive
```

Generated artifacts:

```text
/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones/kdenlive_mcp_real_validation_rough_cut_plan.rough-cut-plan.json
/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones/kdenlive_mcp_real_validation_timeline.timeline.json
/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones/kdenlive_mcp_real_validation.kdenlive
```

Result:

```text
workflow success: true
planned_duration: 8.0
selected_segment_count: 1
track_count: 2
clip_count: 2
marker_count: 1
guide_count: 1
bin_media_count: 1
timeline_clip_count: 2
missing_media_count: 0
MLT load check: valid true
warnings: none
media_checksums_unchanged: true
```

Decision:

```text
The real user media folder validation gate is satisfied for commit 4bdcd70.
Manual Kdenlive visual verification is satisfied by the 2026-08-25 screenshot
recorded below.
```

Manual verification command:

```bash
flatpak run org.kde.kdenlive \
  "/home/abrahamc/Descargas/Investigación PLINK/Vídeos muestra_análisis de aplicaciones/kdenlive_mcp_real_validation.kdenlive"
```

## 2026-08-25 Manual Kdenlive Visual Verification

Validated commit:

```text
1f65a9a
```

Machine date:

```text
2026-08-25T23:41:31-05:00
```

Screenshot:

```text
/home/abrahamc/Imágenes/Capturas de pantalla/Captura de pantalla_20260825_234056.png
```

Observed result:

```text
Kdenlive opened kdenlive_mcp_real_validation.kdenlive.
Project profile is Vertical HD 30 fps.
Project Bin contains Secuencia 1 and Video 1 [Estadísticas].
The media item shows duration 00:00:08:00.
Timeline contains an editable video clip on V2.
Guide/marker rough_001 is visible above the timeline.
The timeline duration shown by Kdenlive is 00:00:08:00.
No offline-media warning is visible in the screenshot.
```

Note:

```text
The Project Monitor is black because the visible playhead is beyond the
generated 8-second clip duration, not because the media failed to load.
```

Decision:

```text
Manual Kdenlive visual verification is satisfied for the generated real-user
validation project.
```

## 2026-08-26 Edited Timeline Export Validation

Scope:

```text
P2 editing surface expansion
```

Validated behavior:

```text
trim_timeline_clip copy-on-write JSON mutation
move_timeline_clip copy-on-write JSON mutation
split_timeline_clip copy-on-write JSON mutation
apply_timeline_edits batch copy-on-write JSON mutation
edit_timeline_and_export_project composed batch-edit-to-.kdenlive workflow
edited TimelineDocument export to .kdenlive template
KdenliveProjectAdapter inspection of exported trim/move/split projects
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 135 passed in 24.08s
```

Specific integration coverage:

```text
test_export_trimmed_timeline_to_kdenlive_template
test_export_moved_timeline_to_kdenlive_template_preserves_gap
test_export_split_timeline_to_kdenlive_template
test_apply_timeline_edits_writes_single_copy
test_apply_timeline_edits_refuses_invalid_final_timeline
test_apply_timeline_edits_export_to_kdenlive_template
test_edit_timeline_and_export_project_dry_run_does_not_write
test_edit_timeline_and_export_project_writes_timeline_and_project
test_edit_timeline_and_export_project_preflight_refuses_existing_project
test_edit_timeline_and_export_project_reports_failed_edit
```

Decision:

```text
The MCP-owned timeline mutation layer can produce edited timeline JSON copies
that export to structurally valid .kdenlive draft projects for the current
single audio/video track template path.
```

## 2026-08-26 Undo Versioning Workflow Validation

Scope:

```text
P2 operator-level undo/version restore workflow
```

Validated behavior:

```text
clone_project creates incrementing AI copies
restore_project_version copies a selected version into a new restored project
restore_project_version backs up the current project by default
list_project_versions reports AI copies, restored copies, and backups
current project and selected source version remain unchanged
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 136 passed in 21.67s
```

Specific integration coverage:

```text
test_version_restore_flow_lists_restored_project
```

Decision:

```text
Undo is covered as copy-on-write version restore. The MCP creates a new
*_restored_001.kdenlive project instead of overwriting the active project.
```

## 2026-08-26 Timeline Track Operations Validation

Scope:

```text
P2 MCP-owned timeline track management
```

Validated behavior:

```text
create_timeline_track creates audio/video tracks in derived timeline JSON files
update_timeline_track renames, locks, and mutes tracks copy-on-write
remove_timeline_track refuses non-empty tracks by default
remove_timeline_track can remove clips when remove_clips=true
remaining linked clip references are cleared when their linked clip is removed
tools/list exposes the track operation tools
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 140 passed in 29.07s
```

Specific integration coverage:

```text
test_create_timeline_track_writes_copy
test_update_timeline_track_writes_copy
test_remove_timeline_track_refuses_track_with_clips_by_default
test_remove_timeline_track_with_clips_clears_remaining_links
```

Decision:

```text
Track management is available at the MCP-owned TimelineDocument layer. Export
of multiple editable Kdenlive tracks remains a separate P2 writer task.
```

## 2026-08-26 Limited Multi-Track Kdenlive Writer Validation

Scope:

```text
P2 template-backed multi-track writer
```

Validated behavior:

```text
KdenliveProjectAdapter detects multiple editable audio/video playlists
track_v1 preserves the previously validated primary video playlist mapping
additional MCP video tracks map to additional template video playlists
exported .kdenlive inspection includes clips from the extra mapped track
timelines with more tracks than the template supports fail with UNSUPPORTED_TIMELINE
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 142 passed in 26.38s
```

Specific integration coverage:

```text
test_export_timeline_to_kdenlive_template_maps_extra_video_track
test_export_timeline_to_kdenlive_template_refuses_more_tracks_than_template
```

Decision:

```text
The .kdenlive writer can now fill multiple existing editable template tracks.
It still does not synthesize new Kdenlive track structures beyond what the
template provides.
```

## 2026-08-26 Timeline Clip Add Remove Validation

Scope:

```text
P2 MCP-owned timeline clip construction and removal
```

Validated behavior:

```text
add_timeline_clip adds allowed media references to derived timeline JSON files
add_timeline_clip can create linked audio/video clip pairs
add_timeline_clip rejects overlapping output through timeline validation
remove_timeline_clip removes linked pairs when include_linked=true
remove_timeline_clip can remove markers inside removed clip ranges
apply_timeline_edits supports add and remove in the same validated transaction
tools/list exposes add_timeline_clip and remove_timeline_clip
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 146 passed in 31.15s
```

Specific integration coverage:

```text
test_add_timeline_clip_writes_linked_pair
test_add_timeline_clip_reports_overlap
test_remove_timeline_clip_removes_linked_clip_and_marker
test_apply_timeline_edits_can_add_and_remove_clips
```

Decision:

```text
Agents can now build and revise MCP-owned timelines with add, remove, trim,
move, and split operations before exporting to .kdenlive.
```

## 2026-08-26 Timeline Clip Duplicate Validation

Scope:

```text
P2 MCP-owned timeline clip duplication
```

Validated behavior:

```text
duplicate_timeline_clip duplicates clip references copy-on-write
linked audio/video pairs are duplicated together by default
duplicates append to timeline end when timeline_in is omitted
overlapping duplicate requests fail before writing
duplicated timelines export to .kdenlive template
apply_timeline_edits supports duplicate operations
tools/list exposes duplicate_timeline_clip
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 150 passed in 31.70s
```

Specific integration coverage:

```text
test_duplicate_timeline_clip_appends_linked_pair_by_default
test_duplicate_timeline_clip_reports_overlap
test_export_duplicated_timeline_to_kdenlive_template
test_apply_timeline_edits_can_duplicate_clip
```

Decision:

```text
Agents can now duplicate existing timeline clips safely before further trim,
move, split, remove, or export operations.
```

## 2026-08-31 Timeline Gap Validation

Scope:

```text
P2 MCP-owned timeline gap insertion and removal
```

Validated behavior:

```text
insert_timeline_gap shifts later clips copy-on-write
remove_timeline_gap shifts later clips backwards only when the range is empty
gap operations can target all tracks, selected tracks, or one media track type
markers move with gap edits by default
insert_timeline_gap rejects edit points inside clips
remove_timeline_gap rejects non-empty ranges before writing
apply_timeline_edits supports insert_gap and remove_gap operations
gap-edited timelines export to .kdenlive template with blank playlist ranges
tools/list exposes insert_timeline_gap and remove_timeline_gap
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 157 passed in 35.95s
```

Specific integration coverage:

```text
test_insert_timeline_gap_shifts_later_clips_and_markers
test_insert_timeline_gap_rejects_intersecting_clip
test_remove_timeline_gap_shifts_later_clips_and_markers
test_remove_timeline_gap_rejects_non_empty_gap
test_apply_timeline_edits_can_insert_and_remove_gap
test_apply_timeline_edits_reports_invalid_gap_track_ids
test_export_gap_edited_timeline_to_kdenlive_template
```

Decision:

```text
Agents can now open or close empty timeline space without manually moving each
clip, while preserving copy-on-write safety and timeline validation.
```

## 2026-08-31 Timeline Gap Robustness

Scope:

```text
Harden gap operations against invalid timecodes and track selections
```

Validated behavior:

```text
_coerce_finite_float rejects non-finite position and duration values
NaN, inf and -inf never reach gap timeline arithmetic
insert/remove gap return structured INVALID_TIMECODE errors instead of exceptions
track_ids=[] and track_type values without matching tracks are rejected as INVALID_TRACK
apply_timeline_edits reports invalid gap timecodes with failed_step and steps
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 162 passed in 39.32s
```

Specific integration coverage:

```text
test_insert_timeline_gap_rejects_invalid_position
test_remove_timeline_gap_rejects_invalid_duration
test_apply_timeline_edits_reports_invalid_gap_timecode
test_insert_timeline_gap_rejects_empty_track_ids
test_insert_timeline_gap_rejects_track_type_without_matches
```

Decision:

```text
No invalid gap input raises a visible Python exception; every invalid entry
responds with success=false and a structured error code.
```

## 2026-08-31 MCP Tool-Call Exception Boundary

Scope:

```text
Guarantee no tool call can break the MCP server or leak a raw exception
```

Validated behavior:

```text
unexpected handler exceptions return a valid MCP response with isError=true
payload shape is success=false, error=INTERNAL_ERROR, operation=tool_name
no full traceback is exposed to the agent
structured tool results with success=false are not wrapped as INTERNAL_ERROR
tools/list keeps working after an unexpected handler exception
structured log records request_id, operation, error_type, message, duration and success=false
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 165 passed in 28.49s
```

Specific integration coverage:

```text
test_tools_call_wraps_unexpected_exception
test_tools_list_unaffected_by_handler_exception
test_tools_call_logs_unexpected_exception
```

Decision:

```text
Any unhandled Python exception inside a tool handler is converted into a
structured INTERNAL_ERROR response with isError=true, logged without a
traceback, and never breaks the tools/list surface or the server loop.
```

## 2026-08-31 MCP TypeError Boundary Classification

Scope:

```text
Distinguish argument-binding errors from internal handler TypeErrors
```

Validated behavior:

```text
arguments are validated against the handler signature with inspect.signature().bind()
missing or unexpected arguments return JSON-RPC -32602 with "Invalid arguments for <tool>"
a handler that raises TypeError internally with valid arguments returns INTERNAL_ERROR with isError=true
no traceback is exposed in the INTERNAL_ERROR response
structured log records error_type=TypeError and the real internal message
structured tool results with success=false remain unwrapped
tools/list keeps working after an unexpected handler exception
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 168 passed in 29.27s
```

Specific integration coverage:

```text
test_tools_call_reports_missing_argument_as_jsonrpc_error
test_tools_call_internal_type_error_is_not_argument_error
test_tools_call_logs_internal_type_error
```

Decision:

```text
A TypeError raised internally by a handler is no longer misreported as an
argument error. Binding failures stay as JSON-RPC -32602; internal failures
become structured INTERNAL_ERROR responses with isError=true.
```

## 2026-09-01 MCP Tool-Call Argument Parsing

Scope:

```text
Reject non-object tool arguments before handler binding
```

Validated behavior:

```text
arguments=[] is rejected with JSON-RPC -32602
arguments="" is rejected with JSON-RPC -32602
arguments=0 is rejected with JSON-RPC -32602
arguments=False is rejected with JSON-RPC -32602
arguments=None is accepted as {} for MCP tolerance
non-object MCP arguments are rejected before signature binding
structured tool results and internal error handling are unchanged
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 173 passed in 26.89s
```

Specific integration coverage:

```text
test_tools_call_rejects_non_object_arguments
test_tools_call_accepts_none_arguments_as_empty
```

Decision:

```text
Only a JSON object (or None tolerated as an empty object) is accepted for tool
arguments. Any other type fails fast with JSON-RPC -32602 before any handler
signature binding or execution.
```

## 2026-09-01 MCP inputSchema Argument Validation

Scope:

```text
Enforce each tool's declared inputSchema before calling its handler
```

Validated behavior:

```text
missing required properties fail with JSON-RPC -32602 before the handler
unexpected properties fail with additionalProperties=false
wrong property types fail before the handler
invalid enum values fail before the handler
array items are validated recursively against the declared items schema
minItems constraints are enforced for arrays
NaN, inf and -inf are rejected as invalid numbers
None is still tolerated as an empty arguments object
valid calls keep working through the full MCP flow
real tools enforce their schemas (move_timeline_clip, create_timeline_track, apply_timeline_edits)
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 186 passed in 28.61s
```

Specific integration coverage:

```text
test_schema_rejects_missing_required_field
test_schema_rejects_unexpected_property
test_schema_rejects_wrong_type
test_schema_rejects_invalid_enum
test_schema_rejects_array_with_non_string_item
test_schema_accepts_valid_arguments
test_move_timeline_clip_missing_timeline_in_fails_schema
test_create_timeline_track_invalid_enum_fails_schema
test_apply_timeline_edits_empty_edits_fails_schema
test_schema_rejects_non_finite_number
test_move_timeline_clip_rejects_non_finite_timeline_in
```

Decision:

```text
Arguments are validated against the tool's declared inputSchema before handler
signature binding or execution. The contract announced by tools/list is now
enforced at the MCP boundary with a lightweight internal validator, without
adding a JSON Schema dependency.
```

## 2026-09-01 MCP Tool Response Contract Audit

Scope:

```text
Normalize tool response shape so agents can rely on success/operation/error/message
```

Tools reviewed:

```text
environment: health_check, get_environment, get_ffmpeg_version, get_ffprobe_version,
get_mlt_version, get_kdenlive_version
media: get_media_info, scan_media, list_media, validate_media
analysis: extract_frames, detect_black_frames, detect_scene_changes, detect_freeze_frames,
analyze_media, analyze_media_folder
audio: detect_silence, plan_silence_removal
rough_cut: plan_rough_cut, inspect_rough_cut_plan
timeline: inspect_timeline, validate_timeline
manifest: create_manifest, inspect_manifest, validate_manifest
project: inspect_project, validate_project, get_project_lock
workflow: create_vlog_rough_cut_project, edit_timeline_and_export_project
```

Validated behavior:

```text
every executed tool response contains a boolean success
every controlled failure contains error and message strings
every response produced by a handler contains operation naming the tool
schema/protocol errors keep returning JSON-RPC -32602 without operation
environment handlers now return operation directly on success
version tool failures now include message alongside error
server injects operation when a handler omits it (181 error sites audited)
non-dict handler responses become INVALID_TOOL_RESPONSE
dict responses without a boolean success become INVALID_TOOL_RESPONSE
failures missing error or message become INVALID_TOOL_RESPONSE
operation values that are not non-empty strings become INVALID_TOOL_RESPONSE
valid controlled errors and INTERNAL_ERROR responses are preserved
```

Inconsistencies corrected:

```text
operation was missing on all error responses (~181 _error call sites)
operation was missing on health_check, get_environment and version tool successes
get_ffmpeg/get_ffprobe/get_mlt/get_kdenlive version failures lacked message
malformed handler responses previously could leak to the agent
```

Command:

```bash
scripts/dev_check.sh
```

Result:

```text
compileall: passed
pytest: 200 passed in 29.65s
```

Specific integration coverage:

```text
test_all_tool_definitions_declare_object_schema_and_handler
test_cheap_tool_success_responses_meet_contract
test_controlled_error_responses_meet_contract
test_environment_handlers_include_operation_directly
test_version_tool_failure_includes_error_message_and_operation
test_mcp_boundary_guarantees_success_for_malformed_responses
test_non_dict_handler_response_becomes_invalid_tool_response
test_dict_without_success_becomes_invalid_tool_response
test_failure_without_error_becomes_invalid_tool_response
test_valid_response_without_operation_gets_operation_injected
test_controlled_error_response_is_not_converted
test_non_string_operation_becomes_invalid_tool_response
test_empty_operation_becomes_invalid_tool_response
test_invalid_operation_on_failure_becomes_invalid_tool_response
```

Decision:

```text
The MCP boundary guarantees that every handler-produced response carries a
boolean success, that failures carry error and message, and that operation names
the invoked tool. Fixes were applied at the service level where cheap
(environment tools) and a minimal operation injection was added in the server
because correcting ~181 error sites across eight modules would be a large refactor.
```

## 2026-09-01 Real MLT Load Validation Gate

Scope:

```text
Real, non-mocked MLT/Kdenlive load validation for an MCP-generated .kdenlive
```

Project used:

```text
/data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive
generated by create_vlog_rough_cut_project (folder=examples/recon,
template=manual_empty_vertical.kdenlive, target_duration=4)
```

Artifact persistence:

```text
persisted: yes, the generated project is kept in the repository at
examples/recon/mlt_gate_20260901.kdenlive as a gate fixture so the documented
MLT check command is reproducible against a known-good MCP-generated draft.
```

Environment:

```text
Kdenlive Flatpak: org.kde.kdenlive (kdenlive_version 26.04.3 in project)
melt host binary: not installed; validated through Flatpak melt
```

Command (documented gate):

```bash
KDENLIVE_MCP_RUN_MLT_CHECK=1 \
KDENLIVE_MCP_MLT_PROJECT=/data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive \
scripts/dev_check.sh
```

Raw melt invocation:

```bash
flatpak run --command=melt org.kde.kdenlive \
  /data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive \
  -consumer null terminate_on_pause=1
```

Result:

```text
gate exit: 0
pytest: 205 passed
raw melt exit: 0 (project consumed to 100% frame timeline)
```

Structured validation (`validate_project` with `check_mlt=True`):

```text
success: true
valid: true
checks.mlt_load: checked true, valid true, status loaded, returncode 0
summary: profile vertical_hd_30, kdenlive_version 26.04.3
media_count: 2, sequence_count: 1, missing_media_count: 0
```

Decision:

```text
A real, non-mocked MLT/Kdenlive load validation passed for an MCP-generated
.kdenlive draft using the installed Flatpak melt. The optional workflow-level
MLT load requirement moves from PARTIAL to DONE in the production readiness
matrix.
```
