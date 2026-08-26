# Release Checklist

Use this checklist before labeling a build as
`production-local-agent-single-user`.

The release is not approved until every required result is recorded in the
release notes or commit notes.

## 1. Repository State

Record:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Required result:

```text
working tree clean
release commit identified
no untracked generated artifacts
```

## 2. Deterministic Local Checks

Run:

```bash
scripts/dev_check.sh
```

Required result:

```text
compileall passes
pytest passes
```

Record the exact pytest count.

## 3. Fixture Workflow Check

Run:

```bash
KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW=1 scripts/dev_check.sh
KDENLIVE_MCP_RUN_RELIABILITY=1 scripts/dev_check.sh
```

Required result:

```text
workflow success true
rough_cut_plan artifact created
timeline artifact created
.kdenlive artifact created
timeline_clip_count > 0
marker_count > 0
guide_count > 0
missing_media_count == 0
temporary fixture artifacts cleaned up
```

## 4. Flatpak MLT Load Check

Generate a project in an allowed directory, then run:

```bash
flatpak run --command=melt org.kde.kdenlive \
  /path/to/generated.kdenlive \
  -consumer null terminate_on_pause=1
```

Required result:

```text
exit code 0
no MLT project-load error
```

Qt session-management warnings are acceptable if the process exits with code 0.

## 5. Manual Kdenlive Open Check

Open the same generated project:

```bash
flatpak run org.kde.kdenlive /path/to/generated.kdenlive
```

Required manual result:

```text
project opens
media appears in Project Bin
timeline contains editable audio/video clips
guides/markers identify rough-cut review segments
playback starts without offline-media errors
original media files remain unchanged
```

Record:

```text
project path
Kdenlive version
media folder used
manual result
any warnings observed
```

## 6. Original Media Integrity

For the fixture workflow this is covered by automated tests. For a real user
media folder, record hashes before and after:

```bash
find /path/to/media -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' \) \
  -print0 | sort -z | xargs -0 sha256sum > before.sha256

# run workflow

find /path/to/media -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' \) \
  -print0 | sort -z | xargs -0 sha256sum > after.sha256

diff -u before.sha256 after.sha256
```

Required result:

```text
diff has no changes
```

## 7. MCP Agent Check

Use the configured Codex MCP server and call:

```text
tools/list
health_check
get_environment
create_vlog_rough_cut_project
```

Required result:

```text
tools/list includes production tool set
health_check success true
get_environment shows intended allowlists
workflow returns success true or structured warning for sandbox-only MLT limits
logs contain one JSONL record per tool call
```

## 8. Undo / Version Restore Check

Run or verify the project-version flow:

```text
clone_project
list_project_versions
restore_project_version
list_project_versions
```

Required result:

```text
current project remains unchanged
selected version is copied into a new *_restored_001.kdenlive file
backup is created before restore unless explicitly disabled
restored project validates
version list includes AI and restored copies
```

## 9. Release Evidence Template

Copy this into release notes:

```text
Release target:
Commit:
Date:
Machine:
Kdenlive:
FFmpeg:
MLT:

scripts/dev_check.sh:

KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW=1 scripts/dev_check.sh:

Flatpak melt project:
Flatpak melt result:

Manual Kdenlive project:
Manual Kdenlive result:

Original media integrity result:
Undo/version restore result:

Known warnings:
Decision:
```

## Failure Policy

Any failure in deterministic checks blocks release.

Manual Kdenlive-open failure blocks release.

Flatpak sandbox failure blocks release only when it happens outside the known
Codex command sandbox. Inside the Codex sandbox, it must be recorded as
`FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX` and then rechecked outside the
sandbox.
