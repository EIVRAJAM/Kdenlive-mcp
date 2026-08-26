#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export KDENLIVE_MCP_LOG_FILE="${KDENLIVE_MCP_LOG_FILE:-off}"

python3 -m compileall src
python3 -m pytest

if [[ "${KDENLIVE_MCP_RUN_FIXTURE_WORKFLOW:-0}" == "1" ]]; then
  export KDENLIVE_MCP_ALLOWED_MEDIA_DIRS="$REPO_ROOT/examples/recon"
  export KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS="$REPO_ROOT/examples/recon"
  export KDENLIVE_MCP_ALLOWED_PROJECT_DIRS="$REPO_ROOT/examples/recon"

  python3 - <<'PY'
import json
from pathlib import Path

from kdenlive_mcp.server import handle_request

repo = Path.cwd()
name = "dev_check_workflow"
request = {
    "jsonrpc": "2.0",
    "id": "dev-check",
    "method": "tools/call",
    "params": {
        "name": "create_vlog_rough_cut_project",
        "arguments": {
            "folder": str(repo / "examples" / "recon"),
            "template_project": str(repo / "examples" / "recon" / "manual_empty_vertical.kdenlive"),
            "output_directory": str(repo / "examples" / "recon"),
            "name": name,
            "target_duration": 4,
            "recursive": False,
            "max_files": 2,
            "remove_silence": False,
            "overwrite": True,
            "check_mlt": False,
        },
    },
}

response = handle_request(request)
payload = json.loads(response["result"]["content"][0]["text"])
if not payload.get("success"):
    raise SystemExit(json.dumps(payload, indent=2))
print(json.dumps({
    "success": payload["success"],
    "project": payload["project"],
    "steps": payload["steps"],
}, indent=2))

for suffix in (
    ".kdenlive",
    "_timeline.timeline.json",
    "_rough_cut_plan.rough-cut-plan.json",
):
    path = repo / "examples" / "recon" / f"{name}{suffix}"
    if path.exists():
        path.unlink()
PY
fi

if [[ "${KDENLIVE_MCP_RUN_MLT_CHECK:-0}" == "1" ]]; then
  if [[ -z "${KDENLIVE_MCP_MLT_PROJECT:-}" ]]; then
    echo "KDENLIVE_MCP_MLT_PROJECT is required when KDENLIVE_MCP_RUN_MLT_CHECK=1" >&2
    exit 2
  fi
  flatpak run --command=melt "${KDENLIVE_MCP_FLATPAK_ID:-org.kde.kdenlive}" \
    "$KDENLIVE_MCP_MLT_PROJECT" \
    -consumer null terminate_on_pause=1
fi
