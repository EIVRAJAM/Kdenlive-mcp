from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"

EDIT_OPS = [
    {"operation": "trim", "clip_id": "chain2_v", "source_out": 2.0},
    {"operation": "insert_gap", "position": 2.0, "duration": 0.5},
    {"operation": "split", "clip_id": "chain3_v", "split_at": 4.0},
    {"operation": "fade_in_audio", "clip_id": "chain0_a", "duration_ms": 500},
    {
        "operation": "set_clip_volume_curve",
        "clip_id": "chain0_a",
        "points": [
            {"position_s": 0.0, "value": 0.01},
            {"position_s": 1.0, "value": 0.5},
            {"position_s": 1.8, "value": 0.5},
        ],
    },
]


def _frame(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _read_message(stream) -> dict[str, object] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("ascii").strip().split(":", 1)
        headers[key.lower()] = value.strip()
    length = int(headers["content-length"])
    body = stream.read(length)
    if len(body) != length:
        raise RuntimeError("truncated MCP response body")
    return json.loads(body.decode("utf-8"))


def _call_tool(process, name: str, arguments: dict[str, object]) -> dict[str, object]:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        _frame(
            {
                "jsonrpc": "2.0",
                "id": name,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
    )
    process.stdin.flush()
    response = _read_message(process.stdout)
    assert response is not None
    return json.loads(response["result"]["content"][0]["text"])


def _run_roundtrip(process, tmp_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "roundtrip": None,
        "output_project": None,
        "mlt_load": None,
        "verdict": None,
        "error": None,
    }

    exported = _call_tool(
        process,
        "export_kdenlive_timeline",
        {
            "project": str(SOURCE_PROJECT),
            "output_directory": str(tmp_path),
            "name": "roundtrip_base",
        },
    )
    if not exported.get("success"):
        result["error"] = f"export_kdenlive_timeline failed: {exported.get('error')}"
        return result

    edited = _call_tool(
        process,
        "apply_timeline_edits",
        {
            "timeline_file": exported["timeline_file"],
            "edits": EDIT_OPS,
            "output_directory": str(tmp_path),
            "name": "roundtrip_edited",
            "dry_run": False,
        },
    )
    if not edited.get("success"):
        result["error"] = f"apply_timeline_edits failed: {edited.get('error')}"
        return result

    prepared = _call_tool(
        process,
        "prepare_working_project",
        {
            "project": str(SOURCE_PROJECT),
            "output_directory": str(tmp_path),
            "lock_directory": str(tmp_path / "locks"),
            "owner": "agent",
        },
    )
    if not prepared.get("success"):
        result["error"] = f"prepare_working_project failed: {prepared.get('error')}"
        return result

    applied = _call_tool(
        process,
        "apply_timeline_to_working_project",
        {
            "working_project": prepared["working_project"],
            "timeline_file": edited["timeline_file"],
            "output_directory": str(tmp_path),
            "name": "roundtrip_output",
        },
    )
    if not applied.get("success"):
        result["error"] = f"apply_timeline_to_working_project failed: {applied.get('error')}"
        return result
    result["output_project"] = applied["output_project"]

    validation = _call_tool(
        process,
        "validate_project",
        {"project": result["output_project"], "check_mlt": True, "timeout": 30.0},
    )
    mlt_load = (validation.get("checks") or {}).get("mlt_load")
    result["roundtrip"] = validation.get("valid") is True and bool(mlt_load)
    result["mlt_load"] = mlt_load

    status = (mlt_load or {}).get("status")
    if status == "loaded":
        result["verdict"] = "mlt_loaded"
    elif status == "unavailable":
        result["verdict"] = "mlt_unavailable"
    else:
        result["verdict"] = "mlt_failed"
        result["error"] = (mlt_load or {}).get("error")
    return result


def main() -> int:
    output_root_arg = len(sys.argv) > 1
    output_root = Path(sys.argv[1]).resolve() if output_root_arg else REPO_ROOT / "tmp_out"
    output_root_created = not output_root.exists()
    output_root.mkdir(parents=True, exist_ok=True)

    result: dict[str, object] = {
        "success": False,
        "roundtrip": None,
        "output_project": None,
        "mlt_load": None,
        "verdict": None,
        "error": None,
    }
    try:
        with tempfile.TemporaryDirectory(dir=str(output_root)) as tmp:
            tmp_path = Path(tmp)
            env = dict(os.environ)
            env["KDENLIVE_MCP_ALLOWED_PROJECT_DIRS"] = f"{RECON_DIR}:{tmp_path}"
            env["KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS"] = str(tmp_path)
            env["KDENLIVE_MCP_ALLOWED_MEDIA_DIRS"] = str(RECON_DIR)
            env["KDENLIVE_MCP_LOG_FILE"] = "off"

            command = [sys.executable, str(REPO_ROOT / "src" / "kdenlive_mcp" / "server.py")]
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                cwd=str(REPO_ROOT),
                shell=False,
                env=env,
            )
            try:
                roundtrip = _run_roundtrip(process, tmp_path)
            finally:
                try:
                    process.stdin.close()
                except Exception:
                    pass
                process.wait(timeout=30)

            result.update(roundtrip)
            if roundtrip["verdict"] == "mlt_failed" or roundtrip.get("error"):
                result["success"] = False
            else:
                result["success"] = True
    except Exception as exc:  # keep output structured even on failure
        result["error"] = str(exc)
    finally:
        if output_root_created:
            try:
                output_root.rmdir()
            except OSError:
                pass

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
