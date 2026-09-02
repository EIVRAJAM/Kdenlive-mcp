# Undo And Versioning Workflow

This document defines the safe undo/versioning contract for agent-driven
Kdenlive project edits.

The MCP never restores by overwriting the user's active `.kdenlive` file. Undo
means selecting a previous valid version and copying it into a new restored
project file.

## Principles

```text
never overwrite the active project implicitly
never modify original media
create backups before risky project copy operations
use stable version filenames for AI outputs
validate every source and restored project
keep lock ownership explicit
return structured paths and errors to the agent
```

## File Naming

AI working copies use incrementing filenames:

```text
vlog.kdenlive
vlog_ai_001.kdenlive
vlog_ai_002.kdenlive
vlog_ai_003.kdenlive
```

Restored versions use a separate suffix:

```text
vlog_restored_001.kdenlive
vlog_restored_002.kdenlive
```

Backups are timestamped and normally live under `.backups/`:

```text
.backups/
  vlog_before_clone_2026-08-26_121500_001.kdenlive
  vlog_ai_003_before_restore_2026-08-26_122000_001.kdenlive
```

## Recommended Agent Flow

Before creating an edited project:

```text
prepare_working_project
  -> clone_project
  -> backup_project
  -> lock_project
```

For edits produced from an MCP timeline:

```text
edit_timeline_and_export_project(dry_run=True)
  -> inspect proposed timeline/project paths
edit_timeline_and_export_project(dry_run=False)
  -> writes <name>_timeline.timeline.json
  -> writes <name>.kdenlive
validate_project
```

For applying an MCP timeline to a working copy (copy-on-write spike):

```text
prepare_working_project
  -> working copy <project>_ai_001.kdenlive (locked)
apply_timeline_to_working_project(
  working_project=<project>_ai_001.kdenlive,
  timeline_file=<edited>.timeline.json,
  output_directory=...,
)
  -> writes <project>_ai_001_edited.kdenlive (new derived file)
  -> never modifies the working copy in place
validate_project(<project>_ai_001_edited.kdenlive)
```

The edited copy is a distinct version; the original fixture, the working copy,
and any backups remain untouched. `list_project_versions` and
`restore_project_version` work on the same base stem.

To inspect available undo targets:

```text
list_project_versions
```

To undo to a previous version:

```text
restore_project_version
  project=current_project
  version=selected_previous_project
  suffix="_restored"
```

The result is a new project:

```text
vlog_restored_001.kdenlive
```

The current project remains unchanged, and a backup of it is created unless
`create_backup=false` is explicitly provided.

## MCP Tool Contracts

### prepare_working_project

Use this before a larger edit session. It returns:

```json
{
  "success": true,
  "operation": "prepare_working_project",
  "project": "/home/user/Videos/vlog.kdenlive",
  "working_project": "/home/user/Videos/vlog_ai_001.kdenlive",
  "backup": "/home/user/Videos/.backups/vlog_before_clone_...kdenlive",
  "lock_file": "/home/user/Videos/.locks/vlog_ai_001.kdenlive.lock.json",
  "owner": "codex"
}
```

### list_project_versions

Use this before selecting an undo target. It returns the current project,
working copies, backups, and related project files:

```json
{
  "success": true,
  "operation": "list_project_versions",
  "base_stem": "vlog",
  "working_copy_count": 3,
  "backup_count": 2,
  "working_copies": [],
  "backups": []
}
```

### restore_project_version

Use this to create a restored copy from a selected version:

```json
{
  "success": true,
  "operation": "restore_project_version",
  "project": "/home/user/Videos/vlog_ai_003.kdenlive",
  "version": "/home/user/Videos/vlog_ai_001.kdenlive",
  "restored_project": "/home/user/Videos/vlog_restored_001.kdenlive",
  "backup": "/home/user/Videos/.backups/vlog_ai_003_before_restore_...kdenlive"
}
```

## Failure Rules

The restore flow must fail before writing when:

```text
project is outside allowed_project_directories
version is outside allowed_project_directories
output directory is outside allowed_output_directories
project XML is invalid
version XML is invalid
project or version has missing media references
destination would resolve to the source project
```

Failures must return machine-readable errors such as:

```text
PERMISSION_DENIED
INVALID_PROJECT
MEDIA_OFFLINE
INVALID_OUTPUT
```

## Operator Guidance

After a restore, the user should open the restored project explicitly:

```bash
flatpak run org.kde.kdenlive /home/user/Videos/vlog_restored_001.kdenlive
```

The MCP should not automatically replace which project the user considers
active. The human operator chooses which `.kdenlive` file to continue editing.
