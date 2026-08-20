from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.ffmpeg import detect_silence as ffmpeg_detect_silence
from kdenlive_mcp.security import SecurityError, ensure_media_path
from kdenlive_mcp.tools.media_tools import SUPPORTED_MEDIA_EXTENSIONS, validate_media


SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<start>-?\d+(?:\.\d+)?)")
SILENCE_END_RE = re.compile(
    r"silence_end:\s*(?P<end>-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(?P<duration>-?\d+(?:\.\d+)?)"
)


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _parse_silencedetect_output(output: str) -> list[dict[str, float]]:
    intervals: list[dict[str, float]] = []
    current_start: float | None = None
    for line in output.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group("start"))
            continue

        end_match = SILENCE_END_RE.search(line)
        if not end_match:
            continue
        end = float(end_match.group("end"))
        duration = float(end_match.group("duration"))
        start = current_start if current_start is not None else end - duration
        intervals.append(
            {
                "start": round(start, 6),
                "end": round(end, 6),
                "duration": round(duration, 6),
            }
        )
        current_start = None
    return intervals


def detect_silence(
    media: str,
    threshold_db: float = -35.0,
    minimum_duration: float = 0.8,
) -> dict[str, Any]:
    try:
        path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        return _error("UNSUPPORTED_MEDIA_TYPE", f"Unsupported media extension: {path.suffix}")
    if minimum_duration <= 0:
        return _error("INVALID_ARGUMENT", "minimum_duration must be greater than zero.")
    if threshold_db >= 0:
        return _error("INVALID_ARGUMENT", "threshold_db must be below 0 dB.")

    validation = validate_media(str(path))
    if not validation.get("success"):
        return validation
    if not validation.get("has_audio"):
        return _error("NO_AUDIO_STREAM", f"Media file has no audio stream: {path}")

    result = ffmpeg_detect_silence(Path(path), threshold_db=threshold_db, minimum_duration=minimum_duration)
    output = f"{result.stdout}\n{result.stderr}"
    if not (result.available and result.returncode == 0):
        return _error(
            "FFMPEG_ERROR",
            "FFmpeg silencedetect failed.",
            media=str(path),
            ffmpeg=result.to_dict(),
        )

    silences = _parse_silencedetect_output(output)
    return {
        "success": True,
        "operation": "detect_silence",
        "media": str(path),
        "threshold_db": threshold_db,
        "minimum_duration": minimum_duration,
        "silence_count": len(silences),
        "silences": silences,
        "ffmpeg": result.to_dict(),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "detect_silence": {
        "description": "Detect silence intervals in an allowed media file using FFmpeg silencedetect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "threshold_db": {"type": "number", "default": -35.0},
                "minimum_duration": {"type": "number", "default": 0.8},
            },
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": detect_silence,
    },
}
