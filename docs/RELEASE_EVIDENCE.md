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
