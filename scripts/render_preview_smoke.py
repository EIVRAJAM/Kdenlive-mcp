from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
PROJECT = RECON_DIR / "composite_edit_ai_generated.kdenlive"
OUTPUT_NAME = "render_preview_smoke_output"

MIN_DURATION = 1.0
EXPECTED_WIDTH = 720
EXPECTED_HEIGHT = 1280


def _ffprobe(path: Path) -> tuple[float | None, int | None, int | None]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    if result.returncode != 0:
        return None, None, None
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    duration = float(data.get("format", {}).get("duration", "0") or 0)
    width = height = None
    for stream in streams:
        if stream.get("width"):
            width = int(stream["width"])
            height = int(stream["height"])
            break
    return duration, width, height


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    os.environ["KDENLIVE_MCP_ALLOWED_MEDIA_DIRS"] = str(RECON_DIR)
    os.environ["KDENLIVE_MCP_ALLOWED_PROJECT_DIRS"] = str(RECON_DIR)
    os.environ["KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS"] = str(RECON_DIR)
    os.environ["KDENLIVE_MCP_LOG_FILE"] = "off"

    from kdenlive_mcp.server import handle_request

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "render-smoke",
            "method": "tools/call",
            "params": {
                "name": "render_preview",
                "arguments": {
                    "project": str(PROJECT),
                    "output_directory": str(RECON_DIR),
                    "name": OUTPUT_NAME,
                    "width": EXPECTED_WIDTH,
                    "height": EXPECTED_HEIGHT,
                },
            },
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    output_path = Path(payload.get("output") or RECON_DIR / f"{OUTPUT_NAME}.mp4")

    try:
        if not payload.get("success"):
            error = payload.get("error")
            if error == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX":
                print(json.dumps({"success": False, "blocked": error}, indent=2))
                return 2
            print(json.dumps({"success": False, "error": error, "message": payload.get("message")}, indent=2))
            return 1

        duration, width, height = _ffprobe(output_path)
        ok = duration is not None and duration > MIN_DURATION and width == EXPECTED_WIDTH and height == EXPECTED_HEIGHT
        print(
            json.dumps(
                {
                    "success": ok,
                    "output": str(output_path),
                    "duration": duration,
                    "width": width,
                    "height": height,
                    "expected_width": EXPECTED_WIDTH,
                    "expected_height": EXPECTED_HEIGHT,
                    "min_duration": MIN_DURATION,
                },
                indent=2,
            )
        )
        return 0 if ok else 1
    finally:
        if output_path.exists():
            output_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
