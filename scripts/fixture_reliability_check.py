from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kdenlive_mcp.server import handle_request


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _call_workflow(repo: Path, output_dir: Path, name: str) -> dict[str, Any]:
    request = {
        "jsonrpc": "2.0",
        "id": name,
        "method": "tools/call",
        "params": {
            "name": "create_vlog_rough_cut_project",
            "arguments": {
                "folder": str(repo / "examples" / "recon"),
                "template_project": str(repo / "examples" / "recon" / "manual_empty_vertical.kdenlive"),
                "output_directory": str(output_dir),
                "name": name,
                "target_duration": 4,
                "recursive": False,
                "max_files": 2,
                "remove_silence": False,
                "overwrite": False,
                "check_mlt": False,
            },
        },
    }
    response = handle_request(request)
    if response is None:
        raise RuntimeError("MCP response was empty")
    return json.loads(response["result"]["content"][0]["text"])


def _assert_success(payload: dict[str, Any], iteration: int) -> None:
    if not payload.get("success"):
        raise AssertionError(json.dumps({"iteration": iteration, "payload": payload}, indent=2))
    artifacts = payload["artifacts"]
    for path in artifacts.values():
        if not Path(path).exists():
            raise AssertionError(f"artifact does not exist: {path}")
    if payload["partial_outputs"] != artifacts:
        raise AssertionError("partial_outputs must match artifacts on success")
    if payload["steps"]["timeline"]["clip_count"] <= 0:
        raise AssertionError("timeline must contain clips")
    if payload["steps"]["timeline"]["marker_count"] <= 0:
        raise AssertionError("timeline must contain review markers")
    project_step = payload["steps"]["kdenlive_project"]
    if project_step["timeline_clip_count"] <= 0:
        raise AssertionError("Kdenlive project must contain timeline clips")
    if project_step["guide_count"] <= 0 or project_step["marker_count"] <= 0:
        raise AssertionError("Kdenlive project must contain guides and markers")
    if project_step["missing_media_count"] != 0:
        raise AssertionError("Kdenlive project must not have missing media")


def _assert_overwrite_refusal(repo: Path, output_dir: Path, name: str) -> None:
    payload = _call_workflow(repo, output_dir, name)
    if payload.get("success"):
        raise AssertionError("second workflow call should refuse existing outputs")
    if payload.get("error") != "OUTPUT_EXISTS":
        raise AssertionError(f"expected OUTPUT_EXISTS, got {payload.get('error')}")
    if payload.get("partial_outputs") != {}:
        raise AssertionError("early OUTPUT_EXISTS should not report partial outputs")


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    count = int(os.environ.get("KDENLIVE_MCP_RELIABILITY_RUNS", "20"))
    recon = repo / "examples" / "recon"
    media_files = [recon / "sample1.mp4", recon / "sample_vertical.mp4"]
    before_hashes = {str(path): _sha256(path) for path in media_files}

    os.environ["KDENLIVE_MCP_ALLOWED_MEDIA_DIRS"] = str(recon)
    os.environ["KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS"] = tempfile.gettempdir()
    os.environ["KDENLIVE_MCP_ALLOWED_PROJECT_DIRS"] = f"{recon}:{tempfile.gettempdir()}"
    os.environ.setdefault("KDENLIVE_MCP_LOG_FILE", "off")

    with tempfile.TemporaryDirectory(prefix="kdenlive-mcp-reliability-") as tmp:
        output_dir = Path(tmp)
        runs: list[dict[str, Any]] = []
        for iteration in range(1, count + 1):
            name = f"reliability_{iteration:03d}"
            payload = _call_workflow(repo, output_dir, name)
            _assert_success(payload, iteration)
            _assert_overwrite_refusal(repo, output_dir, name)
            runs.append(
                {
                    "iteration": iteration,
                    "project": payload["project"],
                    "timeline_clip_count": payload["steps"]["kdenlive_project"]["timeline_clip_count"],
                    "marker_count": payload["steps"]["kdenlive_project"]["marker_count"],
                    "guide_count": payload["steps"]["kdenlive_project"]["guide_count"],
                }
            )

    after_hashes = {str(path): _sha256(path) for path in media_files}
    if after_hashes != before_hashes:
        raise AssertionError("original media checksums changed")

    print(
        json.dumps(
            {
                "success": True,
                "operation": "fixture_reliability_check",
                "runs": count,
                "media_checksums_unchanged": True,
                "overwrite_refusal_checked": True,
                "sample": runs[0] if runs else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
