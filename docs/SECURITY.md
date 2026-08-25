# Security

The MCP server is a local automation layer. It must treat every path and tool
argument as untrusted input, even when the caller is an AI agent running on the
same machine.

## Non-Destructive Rule

Original media files must not be modified.

Current enforcement:

```text
generate_thumbnail refuses to write to the input media path
extract_audio refuses to write to the input media path
derived output tools refuse to overwrite existing files
detect_silence is read-only analysis
plan_silence_removal is read-only dry-run planning
extract_frames and generate_contact_sheet create derived outputs only
detect_black_frames is read-only analysis
detect_scene_changes is read-only analysis
detect_freeze_frames is read-only analysis
analyze_media is read-only aggregate analysis
analyze_media_folder is read-only aggregate analysis with an explicit file limit
plan_rough_cut is read-only dry-run planning
save_rough_cut_plan writes only derived JSON plan files in allowed output directories
inspect_rough_cut_plan is read-only and limited to allowed output directories
create_rough_cut_plan_file writes only derived JSON plan files in allowed output directories
create_timeline_from_rough_cut_plan is read-only conversion from allowed output JSON
save_timeline writes only derived JSON timeline files in allowed output directories
inspect_timeline is read-only and limited to allowed output directories
validate_timeline is read-only and checks media references against the media allowlist
export_timeline_to_mlt_xml writes only derived MLT XML drafts in allowed output directories
backup_project creates timestamped copies only
clone_project creates next-version copies only
list_project_versions is read-only
restore_project_version creates restored copies only
lock_project refuses conflicting owners
prepare_working_project clones, backs up, and locks before edits
```

Timeline/project edits must use copy-on-write project files and backups.

## Filesystem Allowlists

The server uses explicit allowlists:

```text
KDENLIVE_MCP_ALLOWED_MEDIA_DIRS
KDENLIVE_MCP_ALLOWED_PROJECT_DIRS
KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS
```

Example:

```bash
export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS=/home/abrahamc/Videos
export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS=/home/abrahamc/Videos:/tmp
```

If no allowlist is configured for a path category, operations in that category
are denied.

## Path Traversal

Paths are expanded and resolved before validation.

Rejected examples:

```text
../../.ssh/id_rsa
/etc/passwd
/home/abrahamc/.ssh/id_ed25519
```

The current error shape is:

```json
{
  "success": false,
  "error": "PERMISSION_DENIED",
  "message": "Path is outside allowed media directories: ..."
}
```

## Subprocess Execution

All subprocess calls must use argument lists:

```python
subprocess.run([...], shell=False)
```

Do not concatenate shell strings from user input.

Current command adapter:

```text
src/kdenlive_mcp/adapters/commands.py
```

## Flatpak Execution

Inside the Codex command sandbox, `flatpak run` can fail with:

```text
error: Unable to allocate instance id
```

The server reports this as:

```text
FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX
```

and falls back to read-only metadata where possible.

This fallback is for discovery only. Render and GUI/project-load operations must
run in a process context where Flatpak execution is permitted.

## Manifest Files

Manifest files are MCP-owned JSON files:

```text
*.kdenlive-mcp.json
```

They are not Kdenlive project files.

Manifest paths are validated against output allowlists. Manifest validation also
checks referenced media file existence and duplicate media IDs.

## Sensitive Data

Do not log or expose:

```text
SSH keys
API tokens
contents of private documents
arbitrary files outside allowlists
```

The project has no persistent log file yet. When logging is added, it should
record operation metadata, paths inside allowlists, durations, and structured
errors, but avoid media content or secrets.

## Future Project Editing Requirements

Before any `.kdenlive` XML mutation exists, implement:

```text
XML validation
reference validation
negative duration checks
gap/timing validation
dry_run support for timeline mutations
```

Copy-on-write project handling, backup creation, and lock files already exist
as separate tools. Never edit the user's active project in place.
