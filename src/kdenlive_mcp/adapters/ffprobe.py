from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.commands import CommandResult, run_command


def ffprobe_json(path: Path, timeout: float = 30.0) -> tuple[CommandResult, dict[str, Any] | None]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        timeout=timeout,
    )
    if not (result.available and result.returncode == 0):
        return result, None
    try:
        return result, json.loads(result.stdout)
    except json.JSONDecodeError:
        return (
            CommandResult(
                command=result.command,
                available=result.available,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                error="Invalid ffprobe JSON output",
            ),
            None,
        )
