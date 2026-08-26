# Production Readiness Contract

This document defines what must be true before `kdenlive-mcp` is considered
ready for real local use by an AI agent.

Production-ready does not mean feature-complete. It means a Codex-like agent can
run the MCP server repeatedly against real local media and produce
Kdenlive-reviewable projects with predictable behavior, clear errors, no
destructive writes, and enough validation for the user to trust the output.

## Production Target

The first production target is:

```text
production-local-agent-single-user
```

Meaning:

```text
local machine only
single human operator
single agent process expected at a time
Kdenlive Flatpak is the visual editor
FFmpeg/ffprobe/MLT are local dependencies
generated projects are drafts for human review
```

Explicitly not included in this production target:

```text
cloud service operation
multi-user collaboration
real-time Kdenlive co-editing
background daemon lifecycle management
full Kdenlive effect/transitions coverage
semantic AI editing quality guarantees
```

## Release Levels

### alpha-local

Useful for development only.

```text
tools exist
fixtures pass
generated drafts can be inspected
manual validation may be required
contracts may still change freely
```

### production-local-agent-single-user

Required before using the MCP as a dependable local editing backend for an
agent.

```text
tool contracts are stable
filesystem boundary is enforced
workflow is end-to-end tested
generated .kdenlive files are validated
original media integrity is tested
failures are structured and actionable
release checklist is reproducible
```

### production-editing-expanded

Required before calling it a broader editing automation layer.

```text
multi-track timeline writing
trim/split/move timeline operations
round-trip tests for real Kdenlive projects
undo/version restore workflow documented
more Kdenlive metadata preserved and updated
```

## Non-Negotiable Principles

```text
local-first
non-destructive
allowlist-bound filesystem access
structured responses
copy-on-write project editing
validated output before success
no GUI automation as the main integration layer
no Kdenlive source fork
```

Any feature that violates these principles is blocked until explicitly
redesigned.

## MUST / SHOULD / COULD

### MUST

These block `production-local-agent-single-user`.

```text
MCP STDIO protocol stability
security allowlists and path traversal rejection
stable tool response/error shapes
media scan and ffprobe validation
Kdenlive project inspect/validate
template-based .kdenlive draft generation
internal TimelineDocument validation
copy-on-write project versioning
project lock handling
rough-cut workflow from folder to .kdenlive
automated end-to-end workflow test
original media checksum test
generated .kdenlive inspect validation
optional workflow-level MLT load validation
partial-output cleanup or explicit partial-output reporting
persistent structured logging
reproducible dev/release check command
schema documentation for persisted JSON files
Codex MCP registration example
known limitations documented
```

### SHOULD

These do not block the first production target, but should be completed soon
after it.

```text
multiple real Kdenlive fixture variants
better Flatpak filesystem diagnostics
tool-level warnings array consistency
release checklist automation where possible
manual Kdenlive-open verification notes per release
clear migration policy for JSON schemas
```

### COULD

These are useful improvements, not production gates.

```text
multi-track editing
transitions
effects
subtitles
proxies
render_preview
render_final
audio ducking
semantic scene selection
AI model integrations
auto reframing
music selection
caption generation
multiple creative edit variants
GUI automation fallbacks
```

## Agent-Safety Contract

Every tool intended for agent use must be safe to call from planning code.

Required behavior:

```text
declare whether it writes files
write only inside allowlisted directories
return absolute paths for artifacts
return machine-readable error codes
return warnings when output is valid but constrained
fail before writing when preflight can detect the issue
refuse overwrite unless overwrite=True
avoid shell=True
avoid stdout logs that corrupt MCP framing
avoid modifying original media
```

For timeline/project mutation tools:

```text
support dry_run or copy-on-write
never edit the user's active project in place
return before/after summaries when changing editing state
validate output before success
include backup/version information when applicable
```

Idempotency requirements:

```text
read-only tools should be idempotent
write tools should refuse existing outputs by default
overwrite=True must be explicit
workflow retries must return OUTPUT_EXISTS instead of silently replacing files
```

## Tool API Stability Contract

Once the project reaches `production-local-agent-single-user`, tools used by the
production workflow must follow these compatibility rules:

```text
do not remove required input fields without a major schema version
do not rename response fields without a major schema version
do not change units silently
do not change success/error semantics silently
additive optional response fields are allowed
new error codes must be documented
persisted JSON schemas must carry schema_version
```

Time units:

```text
MCP API: seconds
internal timeline domain: seconds
Kdenlive adapter boundary: frames/timecode
FFmpeg/ffprobe boundary: native tool units normalized into seconds
```

Path fields:

```text
inputs may be relative only if resolved safely inside an allowlist
outputs returned to agents must be absolute paths
project/media/output paths must be normalized before validation
```

## Required Functional Areas

### 1. MCP Protocol Stability

Required:

```text
initialize
ping
tools/list
tools/call
stable JSON-RPC errors
structured tool schemas
no stdout logging that corrupts MCP framing
```

Acceptance:

```text
Codex can discover every production tool
Codex can call every production tool through STDIO
invalid tool names return structured errors
invalid arguments return structured errors
all tool responses include success or error state
```

### 2. Security Boundary

Required:

```text
allowed_media_directories
allowed_project_directories
allowed_output_directories
path traversal rejection
absolute path normalization
shell=False subprocess execution
overwrite protection by default
```

Acceptance:

```text
../ traversal is rejected
/etc, /usr, /boot, ~/.ssh are rejected unless explicitly allowlisted
outputs outside allowlists are rejected
existing output files are not overwritten unless overwrite=True
original media file checksums remain unchanged after workflows
```

### 3. Environment And Dependency Detection

Required:

```text
python version
ffmpeg version
ffprobe version
MLT/melt version
Kdenlive Flatpak info
Kdenlive Flatpak melt availability
filesystem visibility notes for Flatpak
```

Acceptance:

```text
get_environment returns configured allowlists
get_ffmpeg_version and get_ffprobe_version detect usable binaries
get_mlt_version detects host or Flatpak MLT
get_kdenlive_version reports Flatpak installation state
validation reports when MLT load was skipped and why
```

### 4. Media Intake

Required:

```text
scan_media
list_media
get_media_info
validate_media
generate_thumbnail
extract_audio
stable media IDs
ffprobe metadata normalization
```

Acceptance:

```text
supported video/audio files are discovered recursively when requested
unsupported files are ignored or reported without crashing
duration, resolution, fps, codecs, bitrate, sample rate, channels are returned
offline or unreadable media returns MEDIA_NOT_FOUND or FFMPEG_ERROR
derived thumbnails/audio are written only to allowed output directories
```

### 5. Kdenlive Format Adapter

Required:

```text
single adapter owns all .kdenlive XML knowledge
inspect_project
validate_project
template-based draft writer
round-trip preservation of unknown XML where possible
profile extraction
active sequence detection
editable target playlist detection
guides/markers parsing and writing
```

Acceptance:

```text
fixtures generated by the installed Kdenlive version are parsed
bin media are discovered
timeline clips are discovered
guides and markers are discovered
generated drafts preserve template structure outside controlled edits
generated drafts load through Flatpak melt when available
```

### 6. Internal Timeline Contract

Required:

```text
TimelineDocument
TimelineTrack
TimelineClip
TimelineMarker
stable IDs
seconds as API unit
frame conversion isolated in adapters
overlap validation
duration validation
linked audio/video clip validation
media reference validation
```

Acceptance:

```text
invalid negative times are rejected
source_out <= source_in is rejected
timeline_out <= timeline_in is rejected
duplicate clip/track/marker IDs are rejected
overlapping clips on the same track are reported
linked audio/video clips must match media and timing
```

### 7. Project Versioning And Concurrency

Required:

```text
backup_project
clone_project
list_project_versions
restore_project_version
get_project_lock
lock_project
unlock_project
prepare_working_project
copy-on-write workflow
```

Acceptance:

```text
active user project is not edited in place
AI writes go to derived project paths
backup is created before risky project operations
locked projects reject conflicting writers
stale locks are inspectable and recoverable by owner rules
```

### 8. Rough-Cut Workflow

Required:

```text
detect_silence
plan_silence_removal
plan_rough_cut
save_rough_cut_plan
inspect_rough_cut_plan
create_rough_cut_plan_file
create_timeline_from_rough_cut_plan
save_timeline
inspect_timeline
validate_timeline
export_timeline_to_kdenlive_template
create_vlog_rough_cut_project
```

Acceptance:

```text
workflow returns all generated artifact paths
workflow returns per-step summaries
workflow fails early on invalid permissions
workflow does not leave unreported partial outputs
generated timeline has linked audio/video clips
generated .kdenlive has media in bin and clips in timeline
rough-cut segments are visible as Kdenlive guides/markers
```

### 9. Validation Gate

Required:

```text
xml parse validation
media reference validation
timeline timing validation
MLT load validation when requested and available
clear validation result in workflow response
```

Acceptance:

```text
corrupt XML is rejected
missing media is reported
negative or impossible timings are rejected
MLT load failures make project validation fail when check_mlt=True
the agent receives machine-readable issue codes
```

### 10. Test And Fixture Baseline

Required:

```text
pytest suite
synthetic media fixtures
real Kdenlive fixture projects
integration workflow test
security tests
non-destructive media checksum test
```

Acceptance:

```text
full test suite passes locally
fixtures are small enough for the repo
tests cover denied paths and path traversal
tests cover output overwrite refusal
tests cover generated .kdenlive inspection
at least one generated draft is validated with Flatpak melt in local verification
```

## Mandatory Tool Set

The production core must include these tools:

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
detect_silence
plan_silence_removal
plan_rough_cut
save_rough_cut_plan
inspect_rough_cut_plan
create_rough_cut_plan_file
create_timeline_from_rough_cut_plan
save_timeline
inspect_timeline
validate_timeline
export_timeline_to_kdenlive_template
create_vlog_rough_cut_project
```

`export_timeline_to_mlt_xml` may remain available as a diagnostic/export helper,
but production readiness depends on `.kdenlive` draft generation.

## Measurable Production Gates

All gates below must pass before the release is labeled
`production-local-agent-single-user`.

```text
1. Full pytest suite passes from a clean checkout.
2. End-to-end workflow test generates rough-cut plan, timeline JSON, and .kdenlive.
3. The generated .kdenlive passes inspect_project.
4. The generated .kdenlive passes validate_project(check_mlt=True) on the target machine.
5. Original media checksums before/after the workflow are identical.
6. Running the workflow twice with overwrite=False returns OUTPUT_EXISTS.
7. Path traversal and outside-allowlist tests pass.
8. A generated draft contains at least one bin media item and one timeline clip.
9. A generated rough-cut draft exposes guides/markers for review segments.
10. The release checklist includes a successful manual Kdenlive open verification.
```

Recommended reliability threshold:

```text
the end-to-end local workflow should pass 20 consecutive runs on fixture media
the same workflow should pass on at least one real user media folder
zero original media checksum changes are allowed
zero unstructured tool failures are allowed in production workflows
```

## Required Before Calling It Production

The current codebase has the P0 workflow baseline automated. These gaps should
still be closed before calling it production-ready:

```text
1. Add a sample Codex MCP config file and exact install command.
2. Add versioned schema documentation for rough-cut plan and timeline JSON.
3. Add a Makefile or scripts/dev_check.sh command that runs the accepted checks.
4. Add a release checklist that includes manual Kdenlive open verification.
5. Run and record the 20-pass fixture workflow reliability check.
6. Run and record one real user media folder validation.
```

These are mandatory because they affect agent reliability, user trust, and
recoverability.

## Implementation Order

Work should now follow this order. Do not start optional creative features until
P0 and P1 are complete.

### P0 - Production Gate

```text
automated end-to-end workflow test: implemented
original media checksum assertions: implemented
workflow-level inspect_project validation: implemented through .kdenlive export
workflow-level optional check_mlt validation: implemented
partial-output reporting or cleanup: implemented as explicit partial-output reporting
```

This is the smallest set that turns the current alpha workflow into a dependable
agent workflow. P0 is implemented at test level, but production release still
requires P1 operator-trust work and release evidence.

### P1 - Operator Trust

```text
persistent structured logs: implemented
scripts/dev_check.sh or Makefile validation command
sample Codex MCP config
release checklist with manual Kdenlive open verification
schema docs for rough-cut plan JSON
schema docs for timeline JSON
```

This makes the project operable and debuggable outside a single development
session.

### P2 - Editing Surface Expansion

```text
multi-track writer
trim/split/move operations against TimelineDocument
round-trip tests for gaps and trims
explicit undo/version restore workflow documentation
```

This expands editing ability while staying inside the production contract.

## Agent-Facing Response Contract

Every tool must return structured data. Successful write operations should
include:

```json
{
  "success": true,
  "operation": "operation_name",
  "artifacts": {},
  "summary": {},
  "validation": {},
  "warnings": []
}
```

Failures should include:

```json
{
  "success": false,
  "operation": "operation_name",
  "error": "ERROR_CODE",
  "message": "Human readable message",
  "details": {}
}
```

Workflow failures should also include:

```json
{
  "failed_step": "step_name",
  "step_result": {}
}
```

Standard production workflow error codes:

```text
INVALID_ARGUMENT
INVALID_PROJECT
INVALID_TIMELINE
INVALID_ROUGH_CUT_PLAN
MEDIA_NOT_FOUND
MEDIA_OFFLINE
FFMPEG_ERROR
FFPROBE_ERROR
MLT_ERROR
PROJECT_NOT_FOUND
PROJECT_LOCKED
PERMISSION_DENIED
OUTPUT_EXISTS
PATH_TRAVERSAL
WORKFLOW_STEP_FAILED
```

## Known Accepted Risks

These risks are accepted for `production-local-agent-single-user` but must remain
documented:

```text
Kdenlive project format may change between versions.
Flatpak filesystem access may differ from host filesystem access.
melt load success does not guarantee every UI detail appears exactly as expected.
Variable-frame-rate media may expose timing edge cases.
Metadata rotation and unusual stream layouts may need fixture expansion.
The first production target is single-user, not concurrent multi-agent editing.
```

Unaccepted risks:

```text
silent original media modification
unbounded filesystem access
unvalidated .kdenlive success responses
shell command construction from user input
undocumented response schema changes
```

## Release Checklist

A production-local-agent release must record the exact commands used:

```bash
python3 -m pytest
python3 -m compileall src
```

Project-load validation:

```bash
flatpak run --command=melt org.kde.kdenlive \
  /path/to/generated.kdenlive \
  -consumer null terminate_on_pause=1
```

Manual review:

```bash
flatpak run org.kde.kdenlive /path/to/generated.kdenlive
```

Expected manual result:

```text
project opens
media appears in Project Bin
timeline contains editable audio/video clips
guides/markers identify rough-cut review segments
original media files remain unchanged
```

## Production Readiness Checklist

Do not mark production-ready until all are true:

```text
[ ] MCP tool discovery works from Codex.
[ ] Full pytest suite passes.
[ ] End-to-end workflow test passes.
[ ] Generated .kdenlive validates with inspect_project.
[ ] Generated .kdenlive validates with validate_project(check_mlt=True).
[ ] User can open generated .kdenlive in Kdenlive manually.
[ ] Original media checksums remain unchanged.
[ ] Path traversal tests pass.
[ ] Output overwrite protection tests pass.
[ ] Project locking/versioning tests pass.
[ ] All write tools document dry_run or copy-on-write behavior.
[ ] README contains exact local setup and MCP registration steps.
[ ] Known limitations are documented.
[ ] Release command output is recorded.
```

## Scope Decision

The next implementation work should focus only on P0 and P1. New creative
features should wait unless they directly improve one of the production gates.

Multi-track editing is optional for the first production target, but mandatory
for `production-editing-expanded`.
