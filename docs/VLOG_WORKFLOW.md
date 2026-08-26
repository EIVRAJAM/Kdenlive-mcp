# Vlog Rough-Cut Workflow

This guide shows the current practical path for creating a reviewable Kdenlive
draft from a local folder of videos.

The workflow is non-destructive: original media files are referenced, not
modified. The generated files are derived artifacts:

```text
<name>_rough_cut_plan.rough-cut-plan.json
<name>_timeline.timeline.json
<name>.kdenlive
```

## 1. Choose Paths

Example folder:

```bash
export VLOG_DIR="$HOME/Videos/VlogCentroHistorico"
export TEMPLATE_PROJECT="/data/PROYECTOS/kdenlive-mcp/examples/recon/manual_empty_vertical.kdenlive"
export PROJECT_NAME="vlog_ai_001"
```

Use an output directory Kdenlive Flatpak can read. Prefer a folder under
`$HOME/Videos`; avoid `/tmp` for manual Kdenlive/Flatpak checks.

## 2. Configure Allowlists

The workflow needs media, output, and project permissions:

```bash
export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS="$HOME/Videos"
export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS="$HOME/Videos"
export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS="$HOME/Videos:/data/PROYECTOS/kdenlive-mcp/examples/recon"
export KDENLIVE_MCP_FLATPAK_ID="org.kde.kdenlive"
```

Why `PROJECT_DIRS` includes the repo fixture path: the current writer uses the
real `manual_empty_vertical.kdenlive` template captured during reconnaissance.

## 3. Run The Workflow Tool

From the repo root:

```bash
cd /data/PROYECTOS/kdenlive-mcp
PYTHONPATH=src python3 - <<'PY'
import json
import os

from kdenlive_mcp.server import handle_request

folder = os.environ["VLOG_DIR"]
template = os.environ["TEMPLATE_PROJECT"]
name = os.environ["PROJECT_NAME"]

request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "create_vlog_rough_cut_project",
        "arguments": {
            "folder": folder,
            "template_project": template,
            "output_directory": folder,
            "name": name,
            "target_duration": 60,
            "recursive": True,
            "max_files": 25,
            "remove_silence": True,
            "silence_threshold_db": -35,
            "silence_minimum_duration": 0.8,
            "padding_before": 0.15,
            "padding_after": 0.15,
            "overwrite": False,
            "check_mlt": False,
            "mlt_timeout": 20
        }
    }
}

response = handle_request(request)
payload = json.loads(response["result"]["content"][0]["text"])
print(json.dumps(payload, indent=2, ensure_ascii=False))
PY
```

Expected successful shape:

```json
{
  "success": true,
  "operation": "create_vlog_rough_cut_project",
  "project": "/home/abrahamc/Videos/VlogCentroHistorico/vlog_ai_001.kdenlive",
  "artifacts": {
    "rough_cut_plan": "...rough-cut-plan.json",
    "timeline": "...timeline.json",
    "kdenlive_project": "...kdenlive"
  },
  "steps": {
    "mlt_load": {
      "checked": false,
      "valid": null
    }
  },
  "warnings": []
}
```

If any step fails, the response includes:

```json
{
  "success": false,
  "failed_step": "create_rough_cut_plan_file",
  "error": "OUTPUT_EXISTS",
  "step_result": {},
  "partial_outputs": {}
}
```

Set `check_mlt` to `True` when you want the workflow itself to load-test the
generated project through the Flatpak `melt` binary. In restricted Codex
sandboxes this can be reported as a warning instead of a hard failure.

## 4. Validate With Flatpak Melt

```bash
flatpak run --command=melt org.kde.kdenlive \
  "$VLOG_DIR/$PROJECT_NAME.kdenlive" \
  -consumer null terminate_on_pause=1
```

Exit code `0` means MLT/Kdenlive can load the draft. Qt session-management
warnings are not project-load failures.

## 5. Open In Kdenlive

```bash
flatpak run org.kde.kdenlive "$VLOG_DIR/$PROJECT_NAME.kdenlive"
```

Review the timeline manually. The current writer targets one observed audio
playlist and one observed video playlist from the template. Treat the result as
a rough cut, not as a final edit.

Each rough-cut segment is also written as a Kdenlive guide/marker so the
review points are visible in the generated project.

## Current Limits

```text
one audio/video track pair
template-based .kdenlive draft only
no effects
no transitions
no subtitles
no proxies
no semantic content selection yet
```

The useful next improvement is to generalize the writer to multiple editable
tracks while preserving Kdenlive's native grouping metadata.
