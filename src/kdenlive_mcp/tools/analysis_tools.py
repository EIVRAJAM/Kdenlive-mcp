from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.ffmpeg import extract_frames as ffmpeg_extract_frames
from kdenlive_mcp.adapters.ffmpeg import generate_contact_sheet as ffmpeg_generate_contact_sheet
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path
from kdenlive_mcp.tools.media_tools import SUPPORTED_MEDIA_EXTENSIONS, validate_media


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _safe_prefix(prefix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", prefix.strip())
    return cleaned.strip("._-") or "frame"


def _validate_video_media(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        return _error("UNSUPPORTED_MEDIA_TYPE", f"Unsupported media extension: {path.suffix}")
    validation = validate_media(str(path))
    if not validation.get("success"):
        return validation
    if not validation.get("has_video"):
        return _error("NO_VIDEO_STREAM", f"Media file has no video stream: {path}")
    return None


def extract_frames(
    media: str,
    output_directory: str,
    every_seconds: float = 1.0,
    max_frames: int = 12,
    prefix: str = "frame",
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error
    if every_seconds <= 0:
        return _error("INVALID_ARGUMENT", "every_seconds must be greater than zero.")
    if max_frames <= 0:
        return _error("INVALID_ARGUMENT", "max_frames must be greater than zero.")

    safe_prefix = _safe_prefix(prefix)
    if output_dir.exists() and any(output_dir.glob(f"{safe_prefix}_*.jpg")):
        return _error("OUTPUT_EXISTS", f"Frame outputs already exist for prefix: {safe_prefix}")
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / f"{safe_prefix}_%04d.jpg"
    result = ffmpeg_extract_frames(
        input_path=input_path,
        output_pattern=pattern,
        every_seconds=every_seconds,
        max_frames=max_frames,
    )
    frames = sorted(output_dir.glob(f"{safe_prefix}_*.jpg"))
    success = result.available and result.returncode == 0 and bool(frames)
    return {
        "success": success,
        "operation": "extract_frames",
        "media": str(input_path),
        "output_directory": str(output_dir),
        "every_seconds": every_seconds,
        "max_frames": max_frames,
        "frame_count": len(frames),
        "frames": [str(path) for path in frames],
        "ffmpeg": result.to_dict(),
    }


def generate_contact_sheet(
    media: str,
    output: str,
    every_seconds: float = 1.0,
    columns: int = 3,
    rows: int = 3,
    thumb_width: int = 320,
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
        output_path = ensure_output_path(output)
    except SecurityError as exc:
        return _security_error(exc)
    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error
    if output_path.exists():
        return _error("OUTPUT_EXISTS", f"Output file already exists: {output_path}")
    if output_path == input_path:
        return _error("ORIGINAL_MEDIA_PROTECTED", "Output path cannot be the original media file.")
    if every_seconds <= 0:
        return _error("INVALID_ARGUMENT", "every_seconds must be greater than zero.")
    if columns <= 0 or rows <= 0:
        return _error("INVALID_ARGUMENT", "columns and rows must be greater than zero.")
    if thumb_width <= 0:
        return _error("INVALID_ARGUMENT", "thumb_width must be greater than zero.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = ffmpeg_generate_contact_sheet(
        input_path=input_path,
        output_path=output_path,
        every_seconds=every_seconds,
        columns=columns,
        rows=rows,
        thumb_width=thumb_width,
    )
    return {
        "success": result.available and result.returncode == 0 and output_path.exists(),
        "operation": "generate_contact_sheet",
        "media": str(input_path),
        "output": str(output_path),
        "every_seconds": every_seconds,
        "columns": columns,
        "rows": rows,
        "thumb_width": thumb_width,
        "ffmpeg": result.to_dict(),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "extract_frames": {
        "description": "Extract periodic frames from an allowed video into an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "output_directory": {"type": "string"},
                "every_seconds": {"type": "number", "default": 1.0},
                "max_frames": {"type": "integer", "default": 12},
                "prefix": {"type": "string", "default": "frame"},
            },
            "required": ["media", "output_directory"],
            "additionalProperties": False,
        },
        "handler": extract_frames,
    },
    "generate_contact_sheet": {
        "description": "Generate a contact sheet image from sampled video frames.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "output": {"type": "string"},
                "every_seconds": {"type": "number", "default": 1.0},
                "columns": {"type": "integer", "default": 3},
                "rows": {"type": "integer", "default": 3},
                "thumb_width": {"type": "integer", "default": 320},
            },
            "required": ["media", "output"],
            "additionalProperties": False,
        },
        "handler": generate_contact_sheet,
    },
}
