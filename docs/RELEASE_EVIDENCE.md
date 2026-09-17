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

## 2026-09-01 MCP STDIO Smoke Test

Scope:

```text
Real Content-Length/STDIO server startup, initialize, and tools/list discovery
```

Command:

```bash
python3 scripts/mcp_stdio_smoke_test.py
```

Output:

```json
{
  "success": true,
  "server": "kdenlive-mcp",
  "tool_count": 59,
  "required_tools_present": true,
  "error": null
}
```

Validated behavior:

```text
server starts as a subprocess with shell=False using python3 src/kdenlive_mcp/server.py
initialize returns serverInfo.name == kdenlive-mcp
initialize returns capabilities.tools
tools/list returns a non-empty tool set
health_check, get_environment, scan_media, create_vlog_rough_cut_project and
export_timeline_to_kdenlive_template are present
process exits cleanly (stdin closed, no lingering child)
```

Decision:

```text
An agent can discover tools over the real MCP STDIO channel, not only through
in-process handle_request calls. The smoke test is also integrated behind
KDENLIVE_MCP_RUN_STDIO_SMOKE=1 in scripts/dev_check.sh and as a pytest
(test_mcp_stdio_smoke.py).
```

## 2026-09-01 MCP Project Lock And Restore Workflow

Scope:

```text
End-to-end lock, clone, restore and version listing through handle_request(tools/call)
```

Fixture used:

```text
examples/recon/manual_two_clips_timeline.kdenlive
```

Validated behavior:

```text
lock_project locks a project through the MCP boundary
prepare_working_project refuses to clone a locked project with PROJECT_LOCKED
no working copy is created while the source is locked
unlock_project releases the lock and prepare_working_project then succeeds
clone_project twice creates _ai_001 and _ai_002 versions
list_project_versions sees both working copies
restore_project_version creates _restored_001 from the selected version
the restored .kdenlive parses as XML
the original project checksum is unchanged after clone/restore
restore_project_version with a missing version returns PROJECT_NOT_FOUND
```

Error codes observed:

```text
PROJECT_LOCKED when prepare_working_project targets a locked project
PROJECT_NOT_FOUND when restore_project_version is given a missing version
```

Command:

```bash
pytest tests/test_project_mcp_workflow.py
```

Result:

```text
3 passed
full suite: 209 passed
```

Decision:

```text
Project locks and versioning are now exercised end-to-end at the MCP boundary.
prepare_working_project honors the source lock with a minimal check that refuses
to clone a locked project, closing the earlier lock/versioning e2e gap.
```

## 2026-09-01 MCP Working Copy Edit Flow Restore

Test name:

```text
test_working_copy_edit_flow_restore
```

Commands:

```bash
pytest tests/test_project_mcp_workflow.py
```

Flow validated through handle_request(tools/call):

```text
prepare_working_project creates _ai_001.kdenlive working copy and lock
create_rough_cut_plan_file + create_timeline_from_rough_cut_plan + save_timeline
apply_timeline_edits applies an insert_gap edit to the timeline JSON
export_timeline_to_kdenlive_template uses the working copy as template -> edited .kdenlive
list_project_versions sees the working copy
restore_project_version creates _restored_001 from the working copy
restored .kdenlive parses as XML
original fixture checksum unchanged
all MCP responses carry boolean success and operation
```

Result:

```text
test_working_copy_edit_flow_restore passed
test_direct_kdenlive_working_copy_edit_is_pending skipped (explicit reason)
full suite: 210 passed
```

Technical decision:

```text
No MCP tool edits a .kdenlive working copy in place; editing operates on
MCP-owned .timeline.json documents exported through
export_timeline_to_kdenlive_template using the working copy as template. The e2e
test covers up to that real limit and restore/versioning inside the flow. Direct
in-place .kdenlive editing is recorded as a pending SHOULD in the production
readiness matrix.
```

## 2026-09-01 Kdenlive Fixture Expansion Recon

Fixtures reviewed:

```text
manual_empty_vertical.kdenlive
manual_bin_only.kdenlive
manual_two_clips_timeline.kdenlive
manual_trim_marker.kdenlive
```

Findings from real XML:

```text
default transitions (mix/qtblend) and default filters (volume/panner/audiolevel,
disable=1) are nested inside track tractors with internal_added=237
no existing fixture contains a trimmed clip, a real temporal gap, a user
transition, or a user effect
```

Fixtures created: none. Manual recipes documented for:

```text
manual_trimmed_clip.kdenlive
manual_gap_timeline.kdenlive
manual_transition_dissolve.kdenlive
manual_basic_effect.kdenlive
```

Commands:

```bash
pytest tests/test_kdenlive_project_fixtures.py
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_kdenlive_project_fixtures.py: 8 passed, 8 skipped
tests/test_kdenlive_project_adapter.py + fixtures: 18 passed, 8 skipped
full suite: 213 passed, 9 skipped
```

Technical decision:

```text
The four additional fixtures require a short manual session in Kdenlive 26.04.3;
they are not invented programmatically to avoid guessing Kdenlive XML. Exact
recipes (base file, steps, expected XML pattern, validation command) are recorded
in docs/KDENLIVE_PROJECT_FORMAT.md, and data-driven pattern detectors in
tests/test_kdenlive_project_fixtures.py skip until each file is added.
```

## 2026-09-01 Generic MCP Client Decoupling

Scope:

```text
Decouple client documentation and tests from Codex as the only MCP client
```

Changes:

```text
added docs/MCP_CLIENT_SETUP.md with generic STDIO client configuration
added examples/mcp_client_config.toml (generic example, placeholder paths)
docs/CODEX_SETUP.md kept as a Codex-specific example that references the generic doc
production contract MUST renamed to "generic MCP client registration example"
production readiness matrix row, special-attention item and Top 5 updated to generic
release checklist MCP Agent Check made client-agnostic
README references the generic client setup and keeps Codex as one example
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
pytest tests/test_mcp_client_config.py
pytest
scripts/dev_check.sh
```

Results:

```text
python3 scripts/mcp_stdio_smoke_test.py: success true, tool_count 59
tests/test_mcp_client_config.py: 4 passed
full suite: 214 passed, 9 skipped
```

What the STDIO smoke test covers:

```text
the real Content-Length/STDIO channel, not in-process handle_request calls
initialize + tools/list against the server as a subprocess
serverInfo.name, capabilities.tools and the production tool set
```

What is NOT proven:

```text
exhaustive compatibility with every MCP client implementation; only the real
STDIO MCP protocol was exercised
```

Decision:

```text
The server is MCP-client-agnostic. Codex remains a documented example, not a
system requirement. Any MCP client over STDIO can register the server through
the generic example and docs/MCP_CLIENT_SETUP.md.
```

## 2026-09-01 Residual Codex-Specific Language Removed

Scope:

```text
Remove remaining Codex-specific production language from the contract and checklist
```

Changes:

```text
acceptance criteria that named a specific client as the discovering/calling
party are now generic ("an MCP-capable client can...")
the P1 sample-config item is now a generic MCP client config, with that client
kept as one example
the final checklist discovery item now reads "works from an MCP client"
the production-target description now reads "an MCP-capable agent"
```

Command:

```bash
# grep for the residual Codex-specific phrases (discovery/call/sample-config)
# across docs/ and README.md; the pattern must return no matches
```

Result:

```text
no matches
pytest tests/test_production_readiness_matrix.py tests/test_mcp_client_config.py: 9 passed
full suite: 218 passed, 9 skipped
```

Decision:

```text
Residual Codex-specific production language is removed. Codex remains documented
only as one possible client example; the production target is MCP-client-agnostic.
```

## 2026-09-01 Single Release Gate Command

Command created:

```text
scripts/release_gate.sh
```

Gates covered, in order:

```text
1. dev_check      scripts/dev_check.sh (compileall + pytest)
2. stdio_smoke    KDENLIVE_MCP_RUN_STDIO_SMOKE=1 scripts/dev_check.sh
3. reliability    KDENLIVE_MCP_RUN_RELIABILITY=1 scripts/dev_check.sh
4. mlt_load       KDENLIVE_MCP_RUN_MLT_CHECK=1 (only when KDENLIVE_MCP_MLT_PROJECT is set)
```

Commands executed:

```bash
bash scripts/release_gate.sh
KDENLIVE_MCP_MLT_PROJECT=/data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive bash scripts/release_gate.sh
```

Results:

```text
bash scripts/release_gate.sh: exit 0
  dev_check: OK, stdio_smoke: OK, reliability: OK, mlt_load: SKIPPED
KDENLIVE_MCP_MLT_PROJECT=... bash scripts/release_gate.sh: exit 0
  dev_check: OK, stdio_smoke: OK, reliability: OK, mlt_load: OK
full suite: 223 passed, 9 skipped
```

What remains manual:

```text
Manual Kdenlive open verification stays a separate step (release checklist section 5).
When KDENLIVE_MCP_MLT_PROJECT is unset, the real Flatpak melt load is skipped and
reported explicitly by the gate.
```

Decision:

```text
A single reproducible release gate now runs the deterministic, STDIO, and
reliability gates, plus the optional real MLT load gate, in one command with a
clear summary, failing on any mandatory gate failure.
```

## 2026-09-01 Filesystem Security Boundary Tests

Scope:

```text
Path traversal, symlink, and empty-allowlist behavior for media/project/output
```

Tests added (`tests/test_security.py`):

```text
parent .. traversal rejected for media, project, output
symlink inside an allowed root pointing outside rejected for all three categories
symlink inside an allowed root staying inside accepted and resolves inside
empty allowlist rejects with PERMISSION_DENIED for all three categories
get_media_info via the MCP boundary rejects a symlink escaping the media allowlist
(success=false, error=PERMISSION_DENIED, message, operation)
```

Production change: none.

```text
security.py already resolves paths with Path.resolve(strict=False), which
normalizes .. components and follows symlinks before allowlist comparison.
```

Commands:

```bash
pytest tests/test_security.py tests/test_media_tools.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_security.py + tests/test_media_tools.py: 21 passed
full suite: 236 passed, 9 skipped
```

Decision:

```text
The filesystem boundary is demonstrated for traversal, symlinks that escape an
allowed root, symlinks that stay inside, and empty allowlists, across all three
path categories and through the real MCP channel.
```

## 2026-09-01 Schema Migration Policy Documented

Scope:

```text
Explicit migration policy for persisted MCP JSON files
```

Changes:

```text
docs/SCHEMAS.md gained a "Schema Migration Policy" section covering the version
requirement, compatible v1 changes, incompatible changes requiring v2, agent
policy, and a future migration policy (explicit migrators, dry_run, backup,
round-trip tests)
current error codes are documented (INVALID_ROUGH_CUT_PLAN, INVALID_MANIFEST,
no explicit timeline check) with a TODO to unify on UNSUPPORTED_SCHEMA_VERSION
```

Production change: none.

```text
no migrators were implemented; current formats and schema_version values are unchanged
```

Tests:

```text
tests/test_schema_docs.py (5 tests: policy section, UNSUPPORTED_SCHEMA_VERSION,
dry_run, backup, coverage of rough-cut plan/timeline/manifest kinds)
```

Commands:

```bash
pytest tests/test_schema_docs.py
pytest tests/test_rough_cut_tools.py tests/test_timeline_service.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_schema_docs.py: 5 passed
full suite: 241 passed, 9 skipped
```

Decision:

```text
The migration policy is documented and validated. No implementation changed;
the existing error codes remain and a TODO documents the future unification.
```

## 2026-09-01 Warnings Field Normalized At MCP Boundary

Scope:

```text
Guarantee warnings is always a list in valid tools/call payloads
```

Behavior:

```text
valid tool response without warnings -> warnings: [] injected
valid tool response with warnings list -> preserved
tool response with non-list warnings -> INVALID_TOOL_RESPONSE
controlled error without warnings -> warnings: []
INTERNAL_ERROR -> warnings: []
INVALID_TOOL_RESPONSE -> warnings: []
```

Implementation:

```text
normalized in src/kdenlive_mcp/server.py _call_tool after success/operation
validation and before serialization; _invalid_tool_response and the INTERNAL_ERROR
payload now carry warnings: []; McpError JSON-RPC responses are untouched
```

Tests:

```text
tests/test_server_protocol.py: 6 new warnings cases
tests/test_tool_response_contract.py: MCP boundary assertions now require
warnings to be a list for cheap environment tools, controlled errors, and
INVALID_TOOL_RESPONSE
```

Commands:

```bash
pytest tests/test_server_protocol.py tests/test_tool_response_contract.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_server_protocol.py + tests/test_tool_response_contract.py: 51 passed
full suite: 247 passed, 9 skipped
```

Decision:

```text
A valid tools/call payload now always carries warnings as a list, removing the
per-tool inconsistency without refactoring the tool handlers.
```

## 2026-09-01 Unsupported Schema Version Unified

Scope:

```text
Reject unsupported schema versions in all persisted JSON readers
```

Behavior by JSON type:

```text
rough-cut plan with schema_version != 1 -> UNSUPPORTED_SCHEMA_VERSION
timeline document with schema_version != 1 -> UNSUPPORTED_SCHEMA_VERSION
project manifest with schema_version != "1.0" -> UNSUPPORTED_SCHEMA_VERSION
```

Implementation:

```text
rough_cut_tools.py maps schema_version mismatch to UNSUPPORTED_SCHEMA_VERSION
timeline_service.py raises UnsupportedSchemaVersion in load_timeline_document and
maps it at _load_timeline_from_allowed_output, inspect_timeline, and both export
readers
manifest_service.py raises UnsupportedSchemaVersion in load_manifest and maps it
in inspect_manifest and scan_media_to_manifest
INVALID_ROUGH_CUT_PLAN / INVALID_TIMELINE / INVALID_MANIFEST are kept for
malformed structure unrelated to version
```

Format change: none.

```text
current schema_version values (1 and "1.0") are unchanged; no migrators added
```

Tests:

```text
test_rough_cut_tools.py: schema_version=2 plan -> UNSUPPORTED_SCHEMA_VERSION
test_timeline_service.py: schema_version=2 timeline -> UNSUPPORTED_SCHEMA_VERSION
test_manifest_tools.py: schema_version="2.0" manifest -> UNSUPPORTED_SCHEMA_VERSION
test_tool_response_contract.py: MCP boundary inspect_timeline with schema_version=2
-> success=false, error, message, operation, warnings list
```

Commands:

```bash
pytest tests/test_rough_cut_tools.py tests/test_timeline_service.py tests/test_manifest_tools.py tests/test_tool_response_contract.py
pytest
scripts/dev_check.sh
```

Results:

```text
targeted tests: 79 passed
full suite: 251 passed, 9 skipped
```

Decision:

```text
UNSUPPORTED_SCHEMA_VERSION is now the single structured error for unsupported
schema versions across rough-cut plans, timeline documents and project
manifests, closing the documented TODO without changing current formats.
```

## 2026-09-01 Media Probe Edge Cases

Scope:

```text
VFR, rotation and unusual stream layouts in media scan/ffprobe summary
```

Cases covered (tests/test_media_tools.py, mocked ffprobe payloads):

```text
VFR or ambiguous fps: avg_frame_rate reported, distinct from r_frame_rate
avg_frame_rate invalid ("0/0", "N/A", "") -> fps None
rotation from tags.rotate -> rotation value
rotation from side_data_list Display Matrix -> rotation value
audio-only file -> audio summary, video None
video-only file -> video summary, audio None
multiple streams -> first video and first audio selected
missing bitrate -> bitrate None, no exception
validate_media accepts audio-only and video-only
get_media_info returns success=true with a stable summary for mocked VFR/rotation
```

Production change: minimal.

```text
media_tools.py: fps now treats "0/0" as None (_fps_value); rotation now also
reads side_data_list Display Matrix (_rotation). Existing response shape is
preserved (fps stays a string or None, rotation stays a string or None).
```

Commands:

```bash
pytest tests/test_media_tools.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_media_tools.py: 18 passed
full suite: 264 passed, 9 skipped
```

Decision:

```text
VFR and rotation edge cases are now covered with mocked ffprobe payloads, and
two small gaps (0/0 fps and side_data_list rotation) were fixed without changing
the response shape.
```

## 2026-09-01 Working Copy Edit Spike

Scope:

```text
First minimal spike for direct editing of a .kdenlive working copy
```

Technical decision:

```text
A thin workflow wrapper was implemented: apply_timeline_to_working_project.
It adds a clear semantic contract ("apply this timeline to this working copy"),
copy-on-write derived naming (<working_stem>_edited.kdenlive), a pre-check that
the working copy parses, and optional MLT validation, while reusing
export_timeline_to_kdenlive_template internally (no duplicated XML logic).
True in-place editing of the working copy file is intentionally not done.
```

Contract:

```text
input  working_project .kdenlive (from prepare_working_project)
input  timeline_file .timeline.json (schema_version 1)
output new derived .kdenlive, never the working copy itself
validates the working copy parses before use
returns working_project, output_project, inspection_summary, warnings, operation
check_mlt=true adds an optional Flatpak melt load result
```

Tests:

```text
test_apply_timeline_to_working_project (e2e via MCP):
  working copy created, timeline built, derived .kdenlive written, XML parses,
  inspect_project reports timeline clips, original fixture and working copy
  checksums unchanged
test_apply_timeline_to_working_project_rejects_outside_allowlist: PERMISSION_DENIED
test_apply_timeline_to_working_project_rejects_unsupported_timeline_schema:
  UNSUPPORTED_SCHEMA_VERSION
```

Commands:

```bash
pytest tests/test_project_mcp_workflow.py tests/test_timeline_service.py tests/test_tool_response_contract.py
pytest
scripts/dev_check.sh
```

Results:

```text
targeted tests: 72 passed, 1 skipped
full suite: 267 passed, 9 skipped
tool count: 60 (new tool registered)
```

Decision:

```text
The working-copy editing spike is delivered as a copy-on-write MCP tool. In-place
editing of the working copy file remains a documented future step.
```

## 2026-09-01 apply_timeline_to_working_project check_mlt Semantics

Scope:

```text
Explicit semantics for check_mlt on the working-copy timeline apply wrapper
```

Decision:

```text
check_mlt=true must fail when the real MLT load fails; it stays success=true
with a structured warning when MLT is unavailable due to a known sandbox
(FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX); check_mlt=false runs no MLT.
Error code for a real MLT failure: MLT_ERROR (existing coherent code).
```

Behavior:

```text
check_mlt=false                  -> no validate_project call
check_mlt=true, loaded           -> success=true, mlt_load.valid=true
check_mlt=true, failed           -> success=false, error=MLT_ERROR, warnings=[]
check_mlt=true, unavailable      -> success=true + FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX warning
check_mlt=true, validate fails   -> its structured error is returned
```

Tests:

```text
test_apply_timeline_check_mlt_loaded
test_apply_timeline_check_mlt_failed
test_apply_timeline_check_mlt_unavailable
test_apply_timeline_check_mlt_false_skips_validate
```

Commands:

```bash
pytest tests/test_project_mcp_workflow.py tests/test_timeline_service.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_project_mcp_workflow.py: 12 passed, 1 skipped
full suite: 271 passed, 9 skipped
```

Decision:

```text
check_mlt now has a documented, consistent contract: fail on a real MLT load
failure, succeed with a sandbox warning when unavailable, and skip entirely when
false.
```

## 2026-09-02 Real Kdenlive Fixture Expansion

Fixtures created manually in Kdenlive 26.04.3 and committed:

```text
examples/recon/manual_trimmed_clip.kdenlive
examples/recon/manual_gap_timeline.kdenlive
examples/recon/manual_transition_dissolve.kdenlive
examples/recon/manual_basic_effect.kdenlive
```

XML findings per fixture:

```text
trim:  playlist entry in attribute != 0 (in="00:00:00.633"); entry in/out are
       source ranges, not timeline positions
gap:   <blank length="00:00:01.133"/> elements inside playlist0 and playlist6
dissolve: transition2 mlt_service=composite kdenlive_id=wipe with
       in="00:00:01.567" out="00:00:03.900" and no internal_added=237
effect: filter6 (mlt_service=qtblend) nested inside a playlist entry (clip-level
       filter); default per-track filters never appear inside entries
```

Commands:

```bash
xmllint --noout examples/recon/manual_*.kdenlive
pytest tests/test_kdenlive_project_fixtures.py
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_kdenlive_project_fixtures.py: 17 passed (no skips)
tests/test_kdenlive_project_adapter.py + fixtures: 27 passed
full suite: 279 passed, 1 skipped (only the direct in-place editing skip remains)
```

Decision:

```text
The SHOULD of multiple real Kdenlive fixtures is now closed. The four manual
fixtures exercise real trim/gap/transition/effect XML patterns, the data-driven
detectors pass against them, and the patterns are documented in
docs/KDENLIVE_PROJECT_FORMAT.md. Remaining unknowns are limited to multi-effect
stacks, multiple transitions per clip, proxies, subtitles and round-trip
behavior.
```

## 2026-09-02 Real MCP Client SDK Smoke

Scope:

```text
Separate "the server speaks STDIO correctly" from "a real MCP client SDK can discover it"
```

Environment check:

```text
official Python MCP SDK (mcp): absent
fastmcp: absent
anthropic SDK: absent
openai SDK: installed but this version exposes no MCP client integration
```

Decision:

```text
No usable MCP client SDK is installed locally, and installing one was not
performed (out of scope). A reproducible SDK smoke script was added instead:
scripts/mcp_client_sdk_smoke_test.py. It runs initialize + tools/list through
the official mcp stdio client when the SDK is present, and reports a structured
blocker (exit 2, blocked=mcp-sdk-unavailable) otherwise.
```

Script behavior:

```text
mcp SDK installed -> validates server name kdenlive-mcp, tool_count 60, and the
required minimal tool set (health_check, get_environment, scan_media,
create_vlog_rough_cut_project, apply_timeline_to_working_project)
mcp SDK absent -> exit 2 with blocked=mcp-sdk-unavailable and install hint
```

Commands:

```bash
python3 scripts/mcp_client_sdk_smoke_test.py
python3 scripts/mcp_stdio_smoke_test.py
pytest tests/test_mcp_stdio_smoke.py tests/test_mcp_client_config.py
pytest
scripts/dev_check.sh
```

Results:

```text
python3 scripts/mcp_client_sdk_smoke_test.py: exit 2, blocked=mcp-sdk-unavailable
python3 scripts/mcp_stdio_smoke_test.py: success true, tool_count 60
tests/test_mcp_stdio_smoke.py + tests/test_mcp_client_config.py: 6 passed
full suite: 283 passed, 1 skipped
```

Risk status:

```text
Real-client discovery remains pending until the mcp SDK is installed locally;
the STDIO protocol channel is already validated, and the SDK smoke is
reproducible via "python3 -m pip install 'mcp>=1.0'" + the script.
```

## 2026-09-02 Full Release Gate Re-Run

Scope:

```text
Reproduce the complete release gate against the current repository state
```

Command:

```bash
KDENLIVE_MCP_MLT_PROJECT=/data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive \
  bash scripts/release_gate.sh
```

Result:

```text
exit 0
dev_check:   OK (compileall + pytest)
stdio_smoke: OK
reliability: OK (runs 20, media_checksums_unchanged true, overwrite_refusal_checked true)
mlt_load:    OK (real Flatpak melt run against mlt_gate_20260901.kdenlive, not skipped)
```

Real MLT result:

```text
flatpak run --command=melt org.kde.kdenlive \
  /data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive \
  -consumer null terminate_on_pause=1
exit 0 (project loaded and consumed)
```

Additional commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
python3 scripts/mcp_client_sdk_smoke_test.py
pytest
scripts/dev_check.sh
```

Results:

```text
STDIO smoke: success true, tool_count 60
SDK smoke:   exit 2, blocked=mcp-sdk-unavailable (mcp>=1.0 not installed)
pytest:      283 passed, 1 skipped
dev_check.sh: 283 passed, 1 skipped
git diff --check: clean
```

Decision:

```text
The release gate is reproducible against the current repository state: all
mandatory gates pass, the real MLT load runs (not skipped), and the remaining
SDK-client smoke is blocked only by the absent local mcp SDK. This represents a
release-state run, not just a collection of loose tests.
```

## 2026-09-02 Kdenlive Round-Trip Preparation

Scope:

```text
Prepare and validate an MCP-generated project for a real Kdenlive round-trip
```

Generated project (via existing workflow):

```text
examples/recon/roundtrip_ai_generated.kdenlive
```

Commands:

```bash
# generation
create_vlog_rough_cut_project(folder=examples/recon, template=manual_empty_vertical.kdenlive,
  name=roundtrip_ai_generated, target_duration=4, max_files=2)

# validation before round-trip
xmllint --noout examples/recon/roundtrip_ai_generated.kdenlive
validate_project(check_mlt=True)
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py
```

Results:

```text
xmllint: OK
validate_project: valid=true, MLT load status loaded (Flatpak melt exit 0)
summary: profile vertical_hd_30, media_count 2, sequence_count 1, missing_media_count 0
timeline clips: 4, guides: 2, markers: 2
pytest adapter + fixtures: 27 passed
full suite: 283 passed, 3 skipped (the 2 round-trip tests skip until the resaved file exists)
```

Pending manual step (user):

```text
flatpak run org.kde.kdenlive examples/recon/roundtrip_ai_generated.kdenlive
File > Save As examples/recon/roundtrip_ai_resaved_by_kdenlive.kdenlive
```

Decision:

```text
The MCP-generated project is prepared and fully validated. The round-trip risk
is reduced to a documented manual step: once Kdenlive re-saves the project, the
reproducible tests (test_roundtrip_resaved_project_*) validate that it still
parses, keeps the vertical HD 30 profile, resolves its media, and retains
timeline clips. Byte-identical XML is not expected.
```

## 2026-09-02 Kdenlive Round-Trip Found And Fixed Writer Bug

Scope:

```text
First real Kdenlive round-trip exposed a writer bug that triggered the
"referencia incorrecta en el panel Medios" repair warning
```

Observation:

```text
The user opened roundtrip_ai_generated.kdenlive in Kdenlive 26.04.3, saw the
timeline-reference repair warning, and re-saved it as
roundtrip_ai_resaved_by_kdenlive.kdenlive (used as the oracle, not as success
proof).
```

Root cause:

```text
the writer created a separate timeline chain per audio/video clip, each with a
fresh kdenlive:control_uuid, so Kdenlive could not match them to Project Bin
media and repaired the project
```

Confirmed correct pattern (from the oracle):

```text
one shared timeline chain per media (audio + video playlists reference the same
producer)
timeline chain reuses the bin chain kdenlive:control_uuid for the same media
timeline chains set test_audio=1 and test_image=1
timeline entries carry kdenlive:audio_index=1
```

Fix (src/kdenlive_mcp/adapters/kdenlive_xml.py):

```text
bin and timeline chains of the same media now share one control_uuid
one shared timeline chain per media (set_audio + set_image), not one per clip
timeline entries add kdenlive:audio_index=1
```

Static tests that failed with the old XML and pass after the fix:

```text
test_generated_project_timeline_chains_share_bin_control_uuid
test_generated_project_timeline_entries_have_audio_index
test_generated_project_uses_one_shared_timeline_chain_per_media
test_resaved_project_timeline_chains_share_bin_control_uuid (oracle confirms the invariant)
```

Commands:

```bash
xmllint --noout examples/recon/roundtrip_ai_generated.kdenlive examples/recon/roundtrip_ai_resaved_by_kdenlive.kdenlive
pytest tests/test_kdenlive_project_fixtures.py
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py
pytest
scripts/dev_check.sh
```

Results:

```text
xmllint: OK (both files)
tests/test_kdenlive_project_fixtures.py: 26 passed
tests/test_kdenlive_project_adapter.py + fixtures: 36 passed
full suite: 289 passed, 1 skipped
validate_project(check_mlt=True) on regenerated project: valid, MLT loaded, missing media 0
```

Status:

```text
Manual confirmation (passed): the user reopened the regenerated
roundtrip_ai_generated.kdenlive in Kdenlive 26.04.3 and the "referencia
incorrecta en el panel Medios" dialog no longer appeared. The round-trip writer
bug is corrected and manually confirmed.
```

Decision:

```text
The writer bug that triggered Kdenlive's timeline-reference repair is fixed and
manually verified. roundtrip_ai_resaved_by_kdenlive.kdenlive remains the oracle
of the original bug, not proof of the corrected state. The round-trip risk is
closed for this Kdenlive version; it should be re-verified by release when the
writer changes.
```

## 2026-09-02 Composite Timeline Edit Export

Scope:

```text
Validate the corrected writer against a real edit sequence: trim + gap + split
```

Generated project:

```text
examples/recon/composite_edit_ai_generated.kdenlive
```

Edits applied via the MCP timeline tools:

```text
trim:      clip_001 trimmed to source_out 2.0 (src 0..3 -> 0..2)
insert_gap: 0.5s gap inserted at timeline 2.0 (shifts clip_002)
split:     clip_002 split at timeline 4.0 into part1/part2
```

Validated pattern:

```text
XML well-formed, profile vertical_hd_30, missing_media 0
timeline contains clips (>= 4 entries after split)
at least one trimmed entry (in != 0) and one real <blank length=...>
bin/timeline references coherent: one shared timeline chain per media,
control_uuid shared with the Project Bin, kdenlive:audio_index=1 on entries
```

Commands:

```bash
xmllint --noout examples/recon/composite_edit_ai_generated.kdenlive
flatpak run --command=melt org.kde.kdenlive \
  examples/recon/composite_edit_ai_generated.kdenlive \
  -consumer null terminate_on_pause=1
validate_project(check_mlt=True)
pytest tests/test_kdenlive_project_fixtures.py
```

Results:

```text
xmllint: OK
Flatpak melt: exit 0 (real load)
validate_project: valid=true, mlt_load loaded, missing 0
tests/test_kdenlive_project_fixtures.py: 33 passed
full suite: 296 passed, 1 skipped
```

Decision:

```text
The corrected writer produces valid composite edits (trim + gap + split) with
coherent bin/timeline references and passes real MLT load, without re-introducing
the timeline-reference pattern Kdenlive repairs.
```

## 2026-09-02 render_preview Tool

Scope:

```text
First safe preview render: render_preview for already-validated .kdenlive projects
```

Tool contract:

```text
render_preview(project, output_directory, name=None, width=720, height=1280,
overwrite=False)

command (shell=False via run_command):
  flatpak run --command=melt org.kde.kdenlive <project> \
    -consumer avformat:<output.mp4> width=<w> height=<h> \
    vcodec=libx264 an=0 real_time=-RT
```

Behavior:

```text
ensure_project_path + ensure_output_path
existing output refused unless overwrite=True (OUTPUT_EXISTS)
original .kdenlive never modified
real melt failure -> success=false, error=MLT_ERROR
known sandbox (Unable to allocate instance id) -> success=false,
error=FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX, plus a structured warning with
the same code; success=true is never reported without a generated MP4
response: success, operation, project, output, command_summary, duration_ms, warnings
```

Tests (`tests/test_render_tools.py`):

```text
builds correct Flatpak melt command (shell=False)
rejects existing output without overwrite
respects overwrite=True
rejects paths outside allowlists
reports MLT_ERROR on real failure
reports sandbox unavailable as a structured warning
```

Commands:

```bash
pytest tests/test_render_tools.py
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_render_tools.py: 6 passed
full suite: 302 passed, 1 skipped
tool count: 61 (render_preview registered)
```

Decision:

```text
The MCP can now produce a quick review render from a validated project without
modifying it. render_final and complex presets remain out of scope.
```

## 2026-09-02 render_preview Real Render Investigation

Scope:

```text
Why melt rendered only one frame from MCP-generated projects, and how to make a
real preview render reliable
```

Root cause (one-frame render):

```text
the writer left the project tractor <track producer="tractor4"> in/out and the
main_bin entry for tractor4 at 00:00:00.000, so melt rendered a single frame
```

Fix (src/kdenlive_mcp/adapters/kdenlive_xml.py):

```text
the writer now sets the tractor5 track in/out and the main_bin tractor4 entry
out to the project duration
```

Melt termination (Flatpak):

```text
melt renders all frames but does not exit cleanly and can be killed before the
moov atom is written (48-byte file). Wrapping the command in the coreutils
timeout (SIGTERM) lets melt finalize the MP4. run_command's subprocess.run
timeout would SIGKILL and leave a truncated file.
```

Final render command:

```text
timeout 120 flatpak run --command=melt org.kde.kdenlive <project> \
  -consumer avformat:<output.mp4> real_time=-RT \
  width=720 height=1280 vcodec=libx264 an=0
```

Real smoke (`scripts/render_preview_smoke.py`, opt-in via
`KDENLIVE_MCP_RUN_RENDER_SMOKE=1`):

```text
renders composite_edit_ai_generated.kdenlive and validates the MP4 with ffprobe
```

Commands:

```bash
KDENLIVE_MCP_RUN_RENDER_SMOKE=1 python3 scripts/render_preview_smoke.py
pytest tests/test_render_tools.py
pytest
scripts/dev_check.sh
```

Results:

```text
render smoke: success true, duration 4.56s, width 720, height 1280, exit 0
tests/test_render_tools.py: 7 passed (incl. "returncode 0 but no output -> failure")
full suite: 303 passed, 1 skipped
```

Decision:

```text
render_preview is validated against a real, useful preview render (duration
>1s, requested dimensions) through the opt-in smoke. The writer structural fix
is confirmed, and the melt termination quirk is handled with the timeout
wrapper. render_final and complex presets remain out of scope.
```

## 2026-09-02 Real MCP SDK Client Gate Closed

Scope:

```text
Validate discovery with the official Python MCP SDK, not only the raw STDIO channel
```

Environment:

```text
created an isolated .venv with uv (python3-venv/ensurepip was unavailable) and
installed the official mcp SDK plus pydantic there
```

Findings:

```text
the mcp SDK writes and expects JSONL framing (one JSON message per line), while
the server only supported Content-Length framing; initialize hung
```

Fix (src/kdenlive_mcp/server.py):

```text
the STDIO reader now detects both framings and the writer echoes the framing used
by the client (JSONL or Content-Length); serve() tracks the framing per message
```

Commands:

```bash
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
python3 scripts/mcp_stdio_smoke_test.py
pytest tests/test_server_protocol.py tests/test_mcp_stdio_smoke.py tests/test_mcp_client_config.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
SDK smoke (.venv, mcp 1.9.0): exit 0, success=true, server kdenlive-mcp,
tool_count 61, required_tools_present true
STDIO smoke: success true, tool_count 61
framing unit tests: 53 passed (protocol + smoke + config)
full suite: 310 passed, 1 skipped
```

Decision:

```text
The real MCP SDK client gate is closed: an official mcp client discovers the
server over STDIO. The JSONL framing support is a minimal, backward-compatible
protocol fix. Other clients remain to be sampled, but the SDK that Codex-class
agents use is verified.
```

## 2026-09-14 Post-Commit Release Gate Re-Run

Scope:

```text
Re-run the release gates after committing render_preview and MCP SDK JSONL framing
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
KDENLIVE_MCP_RUN_RENDER_SMOKE=1 scripts/dev_check.sh
KDENLIVE_MCP_MLT_PROJECT=/data/PROYECTOS/kdenlive-mcp/examples/recon/mlt_gate_20260901.kdenlive bash scripts/release_gate.sh
pytest -q
git diff --check
```

Results:

```text
STDIO smoke: success true, tool_count 61
SDK smoke (.venv, official mcp SDK): success true, tool_count 61, missing_tools []
render smoke: blocked inside sandbox, passed outside sandbox with Flatpak/melt,
duration 4.56s, width 720, height 1280
release_gate outside sandbox: dev_check OK, stdio_smoke OK, reliability OK,
mlt_load OK
reliability: 20 runs, media_checksums_unchanged true, overwrite_refusal_checked true
full suite: 312 passed, 1 skipped
dev_check: 312 passed, 1 skipped
git diff --check: clean
temporary preview MP4 cleanup: no residual preview/audit/debug MP4 files in examples/recon
```

Decision:

```text
The post-commit release gate remains green. The render preview gate requires
running outside the command sandbox because Flatpak reports
FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX there, but the real Flatpak/melt render
passes on the target machine. The official SDK client gate and the legacy
Content-Length STDIO smoke both pass with 61 registered tools.
```

## 2026-09-14 apply_edits_to_working_project Orchestration

Scope:

```text
Orchestrate edits on a working copy without the client coordinating timeline JSON + export
```

Tool:

```text
apply_edits_to_working_project(working_project, edits, output_directory=None,
name=None, overwrite=False, dry_run=False, check_mlt=False)
```

Behavior:

```text
validate the working copy (ensure_project_path + parse)
derive the media folder from the working copy's Project Bin
build a rough-cut plan + base MCP timeline from that media
apply edits via apply_timeline_edits
dry_run=true  -> edited timeline plan, no .kdenlive written
dry_run=false -> export via apply_timeline_to_working_project (copy-on-write,
                 XML/reference validation, optional check_mlt)
inner errors are re-wrapped with operation=apply_edits_to_working_project
internal pipeline artifacts use unique per-execution names so a dry_run never
blocks a later real run over the same output_directory
every response carries warning TIMELINE_RECONSTRUCTED_FROM_BIN because the base
timeline is rebuilt from Project Bin media, not the working project's exact
timeline
```

Tests (tests/test_project_mcp_workflow.py):

```text
test_apply_edits_to_working_project_dry_run
test_apply_edits_to_working_project_dry_run_does_not_block_real_run
test_apply_edits_to_working_project_real_flow
test_apply_edits_to_working_project_rejects_existing_output
test_apply_edits_to_working_project_invalid_edit
test_apply_edits_to_working_project_check_mlt_loaded
test_apply_edits_to_working_project_check_mlt_failed
test_apply_edits_to_working_project_check_mlt_unavailable
```

Commands:

```bash
pytest tests/test_project_mcp_workflow.py tests/test_timeline_service.py tests/test_tool_response_contract.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
orchestrated real flow: output .kdenlive exists and XML parses (6 timeline clips)
working copy checksum unchanged
full suite: 320 passed, 1 skipped
tool count: 62 (apply_edits_to_working_project registered)
```

Decision:

```text
A working-copy edit pipeline is now a single MCP tool. The base timeline is
derived from the working copy's media via the existing rough-cut plan path; a
reverse adapter that loads the working copy's exact timeline remains future
work, documented in Remaining Unknowns.
```

## 2026-09-14 Complex Kdenlive Fixture Preparation

Scope:

```text
Prepare detectors and docs for complex real Kdenlive fixtures (pending manual creation)
```

Fixtures targeted:

```text
multiple_effect_stack_on_clip.kdenlive    >=2 user effects on one clip
multiple_transitions_timeline.kdenlive    >=2 user transitions between clips
audio_fade_fixture.kdenlive               audio fade or keyframed volume
proxy_fixture.kdenlive                    generated/attached proxy
```

Status:

```text
none of the four fixtures exist yet; tests test_complex_fixture_* are skipif and
documented recipes are in docs/KDENLIVE_PROJECT_FORMAT.md
```

Detectors added (tests/test_kdenlive_project_fixtures.py):

```text
_has_multiple_effects_on_clip   clip-level filter count >= 2 on one entry
_has_multiple_user_transitions  user transition count >= 2
_has_audio_fade                 best-effort: volume/fade clip filter with keyframed "=" value
_has_proxy_attachment           best-effort: kdenlive:proxy / kdenlive:proxy_metadata on a chain
```

The audio fade and proxy patterns are UNCONFIRMED until the fixtures exist; the
detectors are conservative and documented as best-effort.

Commands:

```bash
pytest tests/test_kdenlive_project_fixtures.py -q
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_kdenlive_project_fixtures.py: 33 passed, 8 skipped (complex fixtures absent)
tests/test_kdenlive_project_adapter.py + fixtures: 43 passed, 8 skipped
full suite: 320 passed, 9 skipped
```

Decision:

```text
Detectors and manual recipes for complex fixtures are ready and skip until the
user creates each fixture in Kdenlive. The exact XML for audio fade and proxy
attachment remains unknown until then.
```

## 2026-09-14 Read-Only Timeline Summary (Reverse-Adapter Phase 1)

Scope:

```text
Read-only extraction of a real .kdenlive timeline before implementing the reverse adapter
```

Method:

```text
KdenliveProjectAdapter.extract_timeline_summary(project)
```

Output structure:

```text
active_sequence_id, fps, profile (width/height/frame_rate)
tracks, timeline_clips (producer, track_kind, media, source in/out,
  duration frames/seconds, position frames/seconds, effect_count)
gaps (playlist_id, track_kind, start, duration)
user_transitions (id, mlt_service, kdenlive_id, in/out, is_user)
clip_effects (entry_producer, filter_id, mlt_service, kdenlive_id)
```

Confirmed vs inferred:

```text
confirmed: active_sequence_id, fps/profile, source in/out, media/resource,
duration_frames, user transitions (no internal_added=237), clip effects (no
internal_added=237), track_kind from hide/audio_track
inferred: position frames/seconds accumulated from entries AND blanks; entry
in/out are source ranges and never used as timeline positions
```

Tests (tests/test_kdenlive_project_adapter.py):

```text
detects trim in manual_trimmed_clip
detects blanks/gaps in manual_gap_timeline
detects user transition in manual_transition_dissolve
detects clip effect in manual_basic_effect
positions accumulate entries+blanks (gap shifts the later clip; source ranges unchanged)
internal_added=237 is never classified as user effect/transition
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_kdenlive_project_adapter.py + fixtures: 51 passed, 8 skipped
full suite: 328 passed, 9 skipped
```

Decision:

```text
The bridge before editing the real timeline is in place: a read-only summary
exposes confirmed and inferred timeline fields, positioning from entries plus
blanks, and user-only transitions/effects. Conversion to TimelineDocument is
deferred until inferred fields are confirmed.
```

## 2026-09-14 inspect_kdenlive_timeline Tool

Scope:

```text
Expose the read-only Kdenlive timeline summary as an MCP tool
```

Tool:

```text
inspect_kdenlive_timeline(project)
```

Behavior:

```text
read-only, no writes, no TimelineDocument conversion
uses KdenliveProjectAdapter.extract_timeline_summary
validates with ensure_project_path (PERMISSION_DENIED / PROJECT_NOT_FOUND / INVALID_PROJECT)
returns success, operation, project, summary, warnings
warning TIMELINE_SUMMARY_HAS_INFERRED_FIELDS when inferred_fields is non-empty
```

Tests:

```text
via handle_request on manual_trimmed_clip.kdenlive: success, operation, clips
non-empty, a source_in_frames != 0, inferred warning present
outside allowlist -> PERMISSION_DENIED
invalid XML -> INVALID_PROJECT
no files written in output dirs
tools/list includes inspect_kdenlive_timeline
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
pytest tests/test_server_protocol.py tests/test_kdenlive_project_adapter.py tests/test_project_mcp_workflow.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
STDIO smoke: success true, tool_count 63
SDK smoke: exit 0, tool_count 63
full suite: 332 passed, 9 skipped
```

Decision:

```text
An agent can now ask "what is actually in the timeline" through the MCP boundary
and reason over confirmed/inferred fields before any edit, without modifying
anything.
```

## 2026-09-14 Reverse Adapter Phase 2 (TimelineDocument Conversion)

Scope:

```text
Safe read-only conversion of a simple .kdenlive to TimelineDocument
```

Method:

```text
KdenliveProjectAdapter.extract_timeline_document(project)
```

Behavior:

```text
uses extract_timeline_summary as the base
rejects user transitions or clip effects with UNSUPPORTED_TIMELINE_FEATURE
converts simple video/audio tracks and clips with resolvable media
source_in/source_out from entry attributes; timeline_in from accumulated
position; gaps/blanks implicit (absence of clips)
stable clip ids derived from producer + track kind
returns a TimelineDocument (schema_version 1) that validates
no writes
```

Tests (tests/test_kdenlive_project_adapter.py):

```text
manual_two_clips_timeline -> valid TimelineDocument (4 clips, 2 tracks)
manual_trimmed_clip -> preserves source_in/source_out
manual_gap_timeline -> preserves accumulated positions (second media shifted)
manual_transition_dissolve -> UNSUPPORTED_TIMELINE_FEATURE
manual_basic_effect -> UNSUPPORTED_TIMELINE_FEATURE
model_validate passes for converted documents
no files written
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest tests/test_timeline_service.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
tests/test_kdenlive_project_adapter.py + fixtures: 57 passed, 8 skipped
full suite: 338 passed, 9 skipped
```

Decision:

```text
The reverse adapter now produces a valid TimelineDocument for simple projects
and refuses complex ones explicitly. It is not yet wired into
apply_edits_to_working_project; that connection is the next step.
```

## 2026-09-14 Orchestration edits over the real timeline

Scope:

```text
apply_edits_to_working_project edits over the working copy's real current
timeline when the project is in the reverse-adapter subset, with a Project Bin
fallback for complex projects.
```

Behavior:

```text
before rebuilding from bin, try extract_timeline_document(working_project)
success -> base timeline saved to a unique internal .timeline.json,
           apply_timeline_edits over it, export; timeline_source=
           "kdenlive_reverse_adapter", warning TIMELINE_LOADED_FROM_KDENLIVE
UNSUPPORTED_TIMELINE_FEATURE -> Project Bin fallback, timeline_source=
           "project_bin_reconstruction", warning TIMELINE_RECONSTRUCTED_FROM_BIN
PROJECT_NOT_FOUND / INVALID_PROJECT -> error, no fallback
clip media resolved to absolute paths via the project bin (resolved_media)
response carries timeline_source; no TIMELINE_RECONSTRUCTED_FROM_BIN when the
reverse adapter is used
```

Tests (tests/test_project_mcp_workflow.py, tests/test_kdenlive_project_adapter.py):

```text
simple working copy -> timeline_source=kdenlive_reverse_adapter, no
  TIMELINE_RECONSTRUCTED_FROM_BIN, output .kdenlive exists and parses
transition/effect working copy -> timeline_source=project_bin_reconstruction +
  TIMELINE_RECONSTRUCTED_FROM_BIN
invalid XML -> INVALID_PROJECT, no fallback
dry_run on simple project -> reverse adapter, no .kdenlive written
dry_run then real run -> still works (unique internal names)
working copy and media not modified
check_mlt loaded/failed/unavailable kept
extract_timeline_document per-playlist tracks, trim/gap/transition/effect tests
  kept
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
pytest tests/test_project_mcp_workflow.py tests/test_kdenlive_project_adapter.py tests/test_timeline_service.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
test_project_mcp_workflow.py: 23 passed, 1 skipped
full suite: 343 passed, 9 skipped
```

Decision:

```text
Simple real projects are no longer edited "blind"; the base timeline is the
working copy's actual current timeline. Complex projects keep the honest
Project Bin fallback with its warning. The Project Bin fallback is retained
until reverse-adapter coverage is complete.
```

## 2026-09-14 Audio/video linking in reverse conversion

Scope:

```text
reverse-converted clips keep audio/video sync through include_linked edits
```

Behavior:

```text
after building clips, extract_timeline_document pairs equivalent audio/video
clips with linked_clip_id in both directions
matching is conservative: same media (or media_id) AND same source_in/source_out
AND same timeline_in/timeline_out AND opposite track types
ambiguous pairing (more than one candidate) -> UNSUPPORTED_TIMELINE_FEATURE,
never a silent guess
video-only/audio-only segments stay unlinked
```

Tests:

```text
test_extract_timeline_document_links_audio_video_pairs:
  manual_two_clips_timeline -> chain0_a<->chain2_v, chain1_a<->chain3_v
test_extract_timeline_document_trim_keeps_links:
  manual_trimmed_clip -> chain0_a<->chain2_v, chain0_a_1<->chain2_v_1,
  chain1_a<->chain3_v
test_apply_edits_to_working_project_reverse_adapter_trims_linked_audio:
  trim chain2_v (dry_run) -> chain0_a also ends at source_out 2.0
transition/effect rejection tests kept
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_project_mcp_workflow.py tests/test_timeline_service.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
adapter + workflow + timeline_service: 110 passed, 1 skipped
full suite: 346 passed, 9 skipped
```

Decision:

```text
The reverse adapter no longer desynchronizes audio/video: equivalent pairs are
linked conservatively and ambiguous cases are refused, so include_linked edits
behave correctly on simple real projects.
```

## 2026-09-14 export_kdenlive_timeline tool

Scope:

```text
read-only/persistent MCP tool that converts a simple .kdenlive to
TimelineDocument and saves it as .timeline.json
```

Behavior:

```text
validate project (ensure_project_path) and output_directory (ensure_output_path)
KdenliveProjectAdapter.extract_timeline_document(project)
unsupported transition/effect -> UNSUPPORTED_TIMELINE_FEATURE, no output written
existing output + overwrite=false -> OUTPUT_EXISTS; overwrite=true replaces
save TimelineDocument as JSON schema_version 1 (save_timeline/load_timeline_document)
no modification of the .kdenlive or its media
response: success, operation, project, timeline_file, timeline, warnings
  [TIMELINE_EXPORTED_FROM_KDENLIVE]
```

Tool count updated 63 -> 64 (scripts/mcp_client_sdk_smoke_test.py,
tests/test_mcp_client_config.py, tests/test_server_protocol.py).

Tests (tests/test_kdenlive_project_adapter.py, tests/test_server_protocol.py):

```text
manual_two_clips_timeline -> valid .timeline.json (fps 30, 4 clips)
manual_trimmed_clip -> preserves source_in/source_out
manual_gap_timeline -> preserves positions with gap (second media shifted)
manual_transition_dissolve -> UNSUPPORTED_TIMELINE_FEATURE, no output
manual_basic_effect -> UNSUPPORTED_TIMELINE_FEATURE, no output
output exists + overwrite=false -> OUTPUT_EXISTS
overwrite=true replaces
project/output outside allowlist -> PERMISSION_DENIED
MCP response shape: success/operation/project/timeline_file/timeline/warnings,
  schema_version 1
tools/list includes export_kdenlive_timeline; tool_count == 64
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
pytest tests/test_project_mcp_workflow.py tests/test_kdenlive_project_adapter.py tests/test_timeline_service.py tests/test_server_protocol.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
server protocol + adapter: full suite 356 passed, 9 skipped
```

Decision:

```text
Any agent can now materialize the working copy's real timeline into the internal
TimelineDocument format before editing, as a reusable piece, without touching
the .kdenlive or its media.
```

## 2026-09-15 Round-trip: read -> edit -> export (e2e via MCP)

Scope:

```text
validate the full inverse cycle using only existing tools, through
handle_request("tools/call")
```

Flow:

```text
export_kdenlive_timeline(manual_two_clips_timeline.kdenlive)
  -> roundtrip_base.timeline.json
apply_timeline_edits(trim chain2_v -> 2.0, insert_gap at 2.0, split chain3_v
  at 4.0)
  -> roundtrip_edited.timeline.json
prepare_working_project -> working copy
apply_timeline_to_working_project(working copy + edited timeline)
  -> roundtrip_output.kdenlive
validate_project(output) -> valid, missing_media_count == 0
inspect_project(output) -> all bin media resource_exists
sha256 of sample1.mp4 and sample_vertical.mp4 unchanged
original fixture and working copy hashes unchanged
```

No new features were needed: the exported timeline already carries absolute
media paths and linked audio/video clips, so the existing edit/export tools
closed the loop without changes. No fixtures or XML were modified.

Tests (tests/test_project_mcp_workflow.py):

```text
test_export_edit_export_roundtrip_via_mcp
```

Commands:

```bash
python3 scripts/mcp_stdio_smoke_test.py
.venv/bin/python scripts/mcp_client_sdk_smoke_test.py
pytest tests/test_project_mcp_workflow.py tests/test_kdenlive_project_adapter.py tests/test_timeline_service.py tests/test_server_protocol.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
full suite: 358 passed, 9 skipped
```

Decision:

```text
An agent can read a real Kdenlive timeline, edit it safely, and return an
editable .kdenlive project — the round-trip is closed with existing tools.
```

## 2026-09-15 Real MLT load of the round-trip output

Scope:

```text
opt-in/reproducible smoke that loads the round-trip output with real melt
(flatpak), not only static validate_project
```

Script:

```text
scripts/roundtrip_mlt_smoke_test.py
  export_kdenlive_timeline -> apply_timeline_edits -> prepare_working_project
  -> apply_timeline_to_working_project -> validate_project(check_mlt=True)
```

Behavior:

```text
spawns the real MCP server over STDIO and drives it with tools/call
mlt_load.status == "loaded"        -> verdict mlt_loaded   (exit 0)
mlt_load.status == "unavailable"   -> verdict mlt_unavailable (exit 0, structured)
mlt_load.status == "failed"        -> verdict mlt_failed   (exit 1, no false success)
the output directory must be readable by the flatpak melt sandbox (e.g. under the
repo); /tmp is typically NOT reachable from the flatpak sandbox and would produce
"Failed to load" with status failed even for a valid project
```

Result (this environment):

```text
flatpak melt available; round-trip output loaded with returncode 0
mlt_load.status == "loaded", valid True
```

Commands:

```bash
python3 scripts/roundtrip_mlt_smoke_test.py
```

Decision:

```text
The round-trip output is not only statically valid: it also loads in a real MLT
runtime when the environment permits. Sandbox/filesystem limitations are
reported structurally (unavailable/failed) instead of as a false success.
```

## 2026-09-15 Round-trip MLT smoke as opt-in release gate

Scope:

```text
wire scripts/roundtrip_mlt_smoke_test.py into scripts/release_gate.sh as an
opt-in gate controlled by an env var
```

Behavior:

```text
KDENLIVE_MCP_RUN_ROUNDTRIP_MLT_SMOKE=1 -> run gate; fails release only if the
  smoke script exits != 0
verdict mlt_loaded or mlt_unavailable -> pass (both structured and honest)
verdict mlt_failed -> exit != 0, blocks the release
env var unset -> explicit "roundtrip_mlt_smoke: SKIPPED" in the gate summary
```

Tests (tests/test_release_gate_script.py):

```text
test_release_gate_contains_expected_gates now also asserts
KDENLIVE_MCP_RUN_ROUNDTRIP_MLT_SMOKE and scripts/roundtrip_mlt_smoke_test.py
```

Commands:

```bash
python3 scripts/roundtrip_mlt_smoke_test.py
bash scripts/release_gate.sh
KDENLIVE_MCP_RUN_ROUNDTRIP_MLT_SMOKE=1 bash scripts/release_gate.sh
pytest tests/test_release_gate_script.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
roundtrip_mlt_smoke_test.py: verdict mlt_loaded (exit 0)
release_gate.sh (unset): roundtrip_mlt_smoke SKIPPED
release_gate.sh (env=1): roundtrip_mlt_smoke OK
```

Decision:

```text
The real round-trip MLT load is now part of the operational release process as
an opt-in gate, without breaking environments where Flatpak/MLT cannot run.
```

## 2026-09-15 Complex Kdenlive fixtures created and patterns confirmed

Scope:

```text
create the four previously pending complex fixtures manually in Kdenlive 26.04.3
and confirm the real XML patterns
```

Fixtures added to `examples/recon/`:

```text
multiple_effect_stack_on_clip.kdenlive
multiple_transitions_timeline.kdenlive
audio_fade_fixture.kdenlive
proxy_fixture.kdenlive
proxy/c50c6384b5a3e673979aec545d5007c6.mov   (generated proxy, 1.8 MB)
```

Confirmed XML patterns (previously UNCONFIRMED):

```text
multiple effects: playlist6 entry with 2 user filters qtblend (Transform) +
  frei0r.contrast0r (Contrast), no internal_added=237
multiple transitions: 2 user transitions with in/out and no internal_added=237
  (luma; frei0r.sleid0r_wipe-down); default mix/qtblend with 237 are ignored
audio fade: clip-level volume filters with keyframed level =
  "00:00:00.000=1;00:00:01.233=50;..." (timecode=value list)
proxy: chain resource = proxy/<hash>.mov with kdenlive:proxy property
  kdenlive:proxy = proxy/<hash>.mov
```

Tests:

```text
tests/test_kdenlive_project_fixtures.py: 43 passed, 0 skipped (was 33 + 8
skipped before the fixtures existed)
full suite: 366 passed, 1 skipped (remaining skip is in-place working copy
editing, unrelated)
```

Commands:

```bash
pytest tests/test_kdenlive_project_fixtures.py -q
pytest
```

Decision:

```text
The four complex scenarios are now covered by real fixtures with confirmed XML
patterns; the detectors no longer rely on unconfirmed assumptions and the
corresponding test skips are gone. The proxy fixture must be committed together
with its generated .mov so the well-formed-with-media check passes elsewhere.
```

## 2026-09-15 Export hardening against complex fixtures

Scope:

```text
confirm export_kdenlive_timeline never silently exports projects with complex
features the reverse adapter cannot represent
```

Behavior:

```text
proxy attachments are now rejected too: extract_timeline_document raises
UNSUPPORTED_TIMELINE_FEATURE when the summary reports proxy_media_ids (bin
chains carrying kdenlive:proxy / kdenlive:proxy_metadata); the summary exposes
proxy_media_ids
without this, proxy_fixture exported success=true with the timeline referencing
the proxy .mov as media (silent semantic loss)
```

Confirmed behavior per complex fixture (via MCP tools/call):

```text
multiple_effect_stack_on_clip  -> UNSUPPORTED_TIMELINE_FEATURE (clip effects)
multiple_transitions_timeline  -> UNSUPPORTED_TIMELINE_FEATURE (user transitions)
audio_fade_fixture             -> UNSUPPORTED_TIMELINE_FEATURE (clip effects)
proxy_fixture                  -> UNSUPPORTED_TIMELINE_FEATURE (proxy attachments)
all: success=false, operation=export_kdenlive_timeline, clear message,
warnings is a list, no .timeline.json written
```

Tests (tests/test_kdenlive_project_adapter.py):

```text
test_export_kdenlive_timeline_rejects_complex_fixture[...] (parametrized over the
4 complex fixtures)
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
adapter + fixtures: 88 passed
full suite: 370 passed, 1 skipped
```

Decision:

```text
The reverse adapter is conservative by design: anything it cannot represent
losslessly (transitions, effects, proxy attachments) is rejected instead of
exported with a silent data loss. The proxy case in particular can never be
mistaken for its proxy .mov.
```

## 2026-09-15 Post-hardening documentation audit

Scope:

```text
align docs/PRODUCTION_READINESS_MATRIX.md with the current state after the
complex fixtures and export hardening landed
```

Changes (docs only, no code):

```text
docs/PRODUCTION_READINESS_MATRIX.md:
  - fixtures complejos ya existen (multiple_effect_stack_on_clip,
    multiple_transitions_timeline, audio_fade_fixture, proxy_fixture) y los
    tests de fixtures ya no tienen skips
  - el pendiente de "crear fixtures complejos" se reemplaza por la
    *escritura/generación MCP* de esas features (hoy rechazadas con
    UNSUPPORTED_TIMELINE_FEATURE sin pérdida silenciosa)
  - los riesgos residuales de efectos/transiciones/fade/proxy quedan acotados a
    escritura MCP pendiente, no a observación XML
  - el veredicto READY se mantiene; los pendientes legítimos son SHOULD
    (escritura MCP de features complejas, edición in-place de working copy,
    segundo cliente MCP)
```

Current test state:

```text
tests/test_kdenlive_project_fixtures.py: 43 passed, 0 skipped
tests/test_kdenlive_project_adapter.py + fixtures: 88 passed
full suite: 371 passed, 1 skipped (only the in-place working copy edit skip)
```

Remaining known skips (legitimate):

```text
test_project_mcp_workflow.py:890: in-place .kdenlive working copy editing is a
pending SHOULD (copy-on-write is the supported path)
```

Commands:

```bash
rg -n "pending|pendiente|skip|UNCONFIRMED|best-effort|fixture.*pending|complex.*pending" docs tests
pytest tests/test_production_readiness_matrix.py tests/test_kdenlive_project_fixtures.py tests/test_kdenlive_project_adapter.py -q
pytest
scripts/dev_check.sh
```

Decision:

```text
Documentation is aligned with the implemented state; remaining pendientes are
writing/generation MCP support (not XML observation), in-place editing, and a
second MCP client — all SHOULD, not MUST. Verdict: READY_WITH_KNOWN_LIMITATIONS.
```

## 2026-09-15 Audio fade write MVP

Scope:

```text
minimal MCP writing support for audio fadein/fadeout over timeline clips, using
the confirmed audio_fade_fixture.kdenlive pattern, without generalizing effects
```

Behavior:

```text
TimelineEffect model (id, kind fadein|fadeout, window_ms) + TimelineClip.effects
(additive field, schema_version stays 1)
apply_timeline_edits gains fade_in_audio / fade_out_audio (clip_id, duration_ms):
  - non-audio clip          -> INVALID_ARGUMENT
  - duplicate same kind     -> INVALID_ARGUMENT
  - window > clip duration  -> INVALID_ARGUMENT
  - dry_run / copy-on-write / error shape same as other edit ops
Kdenlive writer emits a clip-level <filter> volume with
  kdenlive_id=fadein|fadeout; window receives the MCP window_ms value verbatim;
  gain/end fixed per kind (fadein 0->1, fadeout 1->0), kdenlive:collapsed=0
  The exact semantic unit of Kdenlive's window property is not yet confirmed by
  a resave.
export_kdenlive_timeline still rejects clip effects on read (write-only path
for fades for now)
```

Tests:

```text
tests/test_timeline_service.py:
  - TimelineEffect validation (invalid kind, non-positive window)
  - TimelineClip accepts and round-trips effects
  - fade_in_audio/fade_out_audio dry-run (effects in timeline)
  - non-audio clip / duplicate / window exceeding clip -> INVALID_ARGUMENT
  - export writes the expected volume filters and media sha256 unchanged
tests/test_kdenlive_project_fixtures.py:
  - _has_audio_fade recognizes kdenlive_id=fadein/fadeout without keyframes
    (and still ignores a plain volume filter)
tests/test_kdenlive_project_adapter.py:
  - fade_in_audio/fade_out_audio via tools/call MCP boundary
scripts/roundtrip_mlt_smoke_test.py: EDIT_OPS now includes fade_in_audio; the
round-trip output with the fade loads in real melt (mlt_loaded)
```

Commands:

```bash
pytest tests/test_timeline_service.py tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
python3 scripts/roundtrip_mlt_smoke_test.py
pytest
scripts/dev_check.sh
```

Results:

```text
timeline_service + adapter + fixtures: passed
roundtrip_mlt_smoke_test.py: verdict mlt_loaded (output with audio fade loads)
full suite: 385 passed, 1 skipped
```

Decision:

```text
Audio fade writing is available as an MVP: the generated XML matches the
confirmed fixture pattern and the output loads in real MLT. Volume keyframes and
other effects are still write-only-off; export_kdenlive_timeline keeps rejecting
clip effects on read until the reverse adapter learns to read them.
```

## 2026-09-15 Reverse read of simple audio fades

Scope:

```text
export_kdenlive_timeline now accepts simple fadein/fadeout filters and converts
them to TimelineClip.effects, closing the write->read round-trip for the MVP
```

Behavior:

```text
_walk_playlist_summary classifies each clip filter via _classify_audio_fade:
  accept only: audio track entry, mlt_service=volume, kdenlive_id in
  (fadein, fadeout), positive integer window, gain/end expected per kind
  (fadein 0/1, fadeout 1/0), no level keyframes
supported fades are attached directly to the timeline clip as
  supported_audio_fades; clip_effects entries gain a supported flag
extract_timeline_document:
  - rejects when any clip_effect has supported=False (volume keyframes, fades on
    video, other services, wrong gain/end, missing/invalid window)
  - rejects duplicate fade kinds on the same clip
  - converts supported_audio_fades to TimelineEffect
  - TimelineDocument validation remains as a second line of defense
```

Tests:

```text
tests/test_kdenlive_project_adapter.py:
  - roundtrip: export -> fade_in_audio/fade_out_audio -> apply_timeline_to_
    working_project -> export_kdenlive_timeline preserves effects
    (fadein=500, fadeout=400)
  - duplicate fade kind on a clip -> UNSUPPORTED_TIMELINE_FEATURE
  - fade on video track (supported=False) -> UNSUPPORTED_TIMELINE_FEATURE
  - _classify_audio_fade criteria (valid fadein/fadeout, keyframed volume
    rejected, non-audio rejected, wrong gain/end rejected, missing/invalid/zero
    window rejected, other service rejected)
audio_fade_fixture still rejected (has volume keyframes); multiple_effect_stack,
multiple_transitions, proxy fixtures still rejected
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_timeline_service.py tests/test_kdenlive_project_fixtures.py -q
pytest
scripts/dev_check.sh
python3 scripts/roundtrip_mlt_smoke_test.py
```

Results:

```text
adapter + timeline_service + fixtures: passed
full suite: 389 passed, 1 skipped
roundtrip_mlt_smoke_test.py: verdict mlt_loaded
```

Decision:

```text
The fade round-trip is closed: the MCP can write fades, export a .kdenlive, and
read them back as TimelineEffect, while anything outside the strict fade subset
is still refused with UNSUPPORTED_TIMELINE_FEATURE.
```

## 2026-09-16 Audio fade resave verification prepared

Scope:

```text
generate a real .kdenlive with simple fades using MCP tools and prepare skipif
tests + docs for the pending manual Kdenlive resave
```

Behavior:

```text
examples/recon/audio_fade_ai_generated.kdenlive generated via
  export_kdenlive_timeline -> apply_timeline_edits (fade_in_audio 500,
  fade_out_audio 400 on the audio clip) -> apply_timeline_to_working_project
validated:
  xmllint --noout OK
  validate_project(check_mlt=True) -> valid True, mlt status loaded,
    missing_media 0
  XML inspection: filter0 volume/kdenlive_id=fadein window=500 gain=0 end=1,
    filter1 volume/kdenlive_id=fadeout window=400 gain=1 end=0, no level
skipif tests added (active once examples/recon/
  audio_fade_ai_resaved_by_kdenlive.kdenlive exists):
  test_resaved_audio_fade_project_is_well_formed_with_media
  test_resaved_audio_fade_project_reverse_converts_fades (window_ms preserved
    fadein=500, fadeout=400; update assertion if Kdenlive transforms values)
  test_resaved_audio_fade_project_has_no_unexpected_clip_effects
docs/KDENLIVE_PROJECT_FORMAT.md documents the manual step:
  flatpak run org.kde.kdenlive examples/recon/audio_fade_ai_generated.kdenlive
  -> Save As examples/recon/audio_fade_ai_resaved_by_kdenlive.kdenlive
```

Status:

```text
preparation complete; manual resave in Kdenlive is pending (user)
```

Commands:

```bash
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
scripts/dev_check.sh
```

Results:

```text
full suite: 390 passed, 4 skipped (3 new resave skipif + 1 in-place edit skip)
```

Decision:

```text
The MCP-generated audio fade project is valid and loads in real MLT. The next
step is a manual resave in Kdenlive to confirm the window_ms values and filter
shape survive, before expanding to volume keyframes or advanced effects.
```

## 2026-09-16 Audio fade Kdenlive resave verified

Scope:

```text
verify the manually resaved Kdenlive project produced from the MCP-generated
audio fade project
```

Behavior:

```text
the user opened:
  examples/recon/audio_fade_ai_generated.kdenlive
in Kdenlive 26.04.3 and saved it as:
  examples/recon/audio_fade_ai_resaved_by_kdenlive.kdenlive
the first save attempt produced a filename with embedded newlines; it was
renamed to the expected fixture path before validation
the resaved XML preserves the simple fades:
  fadein:  mlt_service=volume, kdenlive_id=fadein,  window=500, gain=0, end=1
  fadeout: mlt_service=volume, kdenlive_id=fadeout, window=400, gain=1, end=0
no level keyframes were introduced for those fades
KdenliveProjectAdapter.extract_timeline_document reads the resaved fades back as
TimelineEffect values with window_ms 500 and 400
all clip_effects in the resaved project are classified as supported
```

Commands:

```bash
xmllint --noout examples/recon/audio_fade_ai_resaved_by_kdenlive.kdenlive
pytest tests/test_kdenlive_project_fixtures.py -q
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
timeout 60 flatpak run --command=melt org.kde.kdenlive \
  examples/recon/audio_fade_ai_resaved_by_kdenlive.kdenlive \
  -consumer null terminate_on_pause=1
```

Results:

```text
xml lint: OK
fixture tests: 49 passed (the 3 audio-fade-resave skipif tests now run)
adapter + fixture tests: passed
full suite: passed with only the existing in-place working-copy skip
real melt load: exit 0
```

Decision:

```text
The simple audio fade loop is now confirmed through a real Kdenlive resave:
write -> open/save in Kdenlive -> read back through the reverse adapter -> load
in melt. Volume keyframes and advanced effects remain intentionally unsupported.
```

## 2026-09-17 Audio volume keyframes Kdenlive resave verified

Scope:

```text
verify that Kdenlive preserves the manual volume-keyframe oracle on resave,
before implementing MCP read/write support for volume curves
```

Behavior:

```text
the user opened:
  examples/recon/audio_fade_fixture.kdenlive
in Kdenlive 26.04.3 and saved it as:
  examples/recon/audio_volume_keyframes_resaved_by_kdenlive.kdenlive
the first save attempt produced a filename with an embedded newline; it was
renamed to the expected fixture path before validation
the resaved XML preserves the keyframed volume filter exactly:
  mlt_service=volume
  kdenlive_id=volume
  window=75
  level=00:00:00.000=1;00:00:01.233=50;00:00:01.833=50;00:00:02.667=50
the same entry still contains the fadein/fadeout filters:
  fadein:  window=75, gain=0, end=1
  fadeout: window=75, gain=1, end=0
kdenlive:activeeffect remains property value 2
the volume-keyframe filter remains classified as unsupported by the simple-fade
reader, as intended
```

Commands:

```bash
xmllint --noout examples/recon/audio_volume_keyframes_resaved_by_kdenlive.kdenlive
pytest tests/test_kdenlive_project_fixtures.py -q
pytest tests/test_kdenlive_project_adapter.py tests/test_kdenlive_project_fixtures.py -q
pytest
timeout 60 flatpak run --command=melt org.kde.kdenlive \
  examples/recon/audio_volume_keyframes_resaved_by_kdenlive.kdenlive \
  -consumer null terminate_on_pause=1
```

Results:

```text
xml lint: OK
fixture tests: 52 passed (the 3 volume-keyframe-resave skipif tests now run)
adapter + fixture tests: passed
full suite: passed with only the existing in-place working-copy skip
real melt load: exit 0
```

Decision:

```text
The XML semantics for Kdenlive volume keyframes are now confirmed through a real
Kdenlive resave. The next implementation can add a strict volume_keyframes
TimelineEffect/read-write path using the preserved level format, while keeping
unsupported curves rejected until explicitly modeled.
```
