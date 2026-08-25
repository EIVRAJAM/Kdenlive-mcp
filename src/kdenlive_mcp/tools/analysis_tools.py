from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.ffmpeg import detect_black_frames as ffmpeg_detect_black_frames
from kdenlive_mcp.adapters.ffmpeg import detect_freeze_frames as ffmpeg_detect_freeze_frames
from kdenlive_mcp.adapters.ffmpeg import detect_scene_changes as ffmpeg_detect_scene_changes
from kdenlive_mcp.adapters.ffmpeg import extract_frames as ffmpeg_extract_frames
from kdenlive_mcp.adapters.ffmpeg import generate_contact_sheet as ffmpeg_generate_contact_sheet
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path
from kdenlive_mcp.tools.audio_tools import detect_silence as audio_detect_silence
from kdenlive_mcp.tools.media_tools import SUPPORTED_MEDIA_EXTENSIONS, scan_media, validate_media


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


BLACKDETECT_RE = re.compile(
    r"black_start:(?P<start>-?\d+(?:\.\d+)?)\s+"
    r"black_end:(?P<end>-?\d+(?:\.\d+)?)\s+"
    r"black_duration:(?P<duration>-?\d+(?:\.\d+)?)"
)
SHOWINFO_PTS_RE = re.compile(r"pts_time:(?P<time>-?\d+(?:\.\d+)?)")
FREEZE_START_RE = re.compile(r"freeze_start:\s*(?P<start>-?\d+(?:\.\d+)?)")
FREEZE_DURATION_RE = re.compile(r"freeze_duration:\s*(?P<duration>-?\d+(?:\.\d+)?)")
FREEZE_END_RE = re.compile(r"freeze_end:\s*(?P<end>-?\d+(?:\.\d+)?)")


def _parse_blackdetect_output(output: str) -> list[dict[str, float]]:
    intervals: list[dict[str, float]] = []
    for line in output.splitlines():
        match = BLACKDETECT_RE.search(line)
        if not match:
            continue
        intervals.append(
            {
                "start": round(float(match.group("start")), 6),
                "end": round(float(match.group("end")), 6),
                "duration": round(float(match.group("duration")), 6),
            }
        )
    return intervals


def _parse_scene_change_output(output: str) -> list[dict[str, float]]:
    changes: list[dict[str, float]] = []
    seen: set[float] = set()
    for line in output.splitlines():
        match = SHOWINFO_PTS_RE.search(line)
        if not match:
            continue
        timestamp = round(float(match.group("time")), 6)
        if timestamp in seen:
            continue
        seen.add(timestamp)
        changes.append({"time": timestamp})
    return changes


def _parse_freezedetect_output(output: str, media_duration: float | None = None) -> list[dict[str, float]]:
    intervals: list[dict[str, float]] = []
    current_start: float | None = None
    current_duration: float | None = None
    for line in output.splitlines():
        start_match = FREEZE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group("start"))
            current_duration = None
            continue

        duration_match = FREEZE_DURATION_RE.search(line)
        if duration_match:
            current_duration = float(duration_match.group("duration"))
            continue

        end_match = FREEZE_END_RE.search(line)
        if not end_match:
            continue
        end = float(end_match.group("end"))
        duration = current_duration if current_duration is not None else None
        start = current_start
        if start is None and duration is not None:
            start = end - duration
        if start is None:
            continue
        if duration is None:
            duration = end - start
        intervals.append(
            {
                "start": round(start, 6),
                "end": round(end, 6),
                "duration": round(duration, 6),
            }
        )
        current_start = None
        current_duration = None
    if current_start is not None and media_duration is not None and media_duration > current_start:
        duration = media_duration - current_start
        intervals.append(
            {
                "start": round(current_start, 6),
                "end": round(media_duration, 6),
                "duration": round(duration, 6),
            }
        )
    return intervals


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


def detect_black_frames(
    media: str,
    minimum_duration: float = 0.5,
    picture_black_ratio: float = 0.98,
    pixel_black_threshold: float = 0.1,
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if minimum_duration <= 0:
        return _error("INVALID_ARGUMENT", "minimum_duration must be greater than zero.")
    if not 0 < picture_black_ratio <= 1:
        return _error("INVALID_ARGUMENT", "picture_black_ratio must be greater than 0 and at most 1.")
    if not 0 <= pixel_black_threshold <= 1:
        return _error("INVALID_ARGUMENT", "pixel_black_threshold must be between 0 and 1.")
    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error

    result = ffmpeg_detect_black_frames(
        input_path=input_path,
        minimum_duration=minimum_duration,
        picture_black_ratio=picture_black_ratio,
        pixel_black_threshold=pixel_black_threshold,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if not (result.available and result.returncode == 0):
        return _error(
            "FFMPEG_ERROR",
            "FFmpeg blackdetect failed.",
            media=str(input_path),
            ffmpeg=result.to_dict(),
        )
    intervals = _parse_blackdetect_output(output)
    return {
        "success": True,
        "operation": "detect_black_frames",
        "media": str(input_path),
        "minimum_duration": minimum_duration,
        "picture_black_ratio": picture_black_ratio,
        "pixel_black_threshold": pixel_black_threshold,
        "black_interval_count": len(intervals),
        "black_intervals": intervals,
        "ffmpeg": result.to_dict(),
    }


def detect_scene_changes(
    media: str,
    threshold: float = 0.35,
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if not 0 < threshold < 1:
        return _error("INVALID_ARGUMENT", "threshold must be greater than 0 and less than 1.")
    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error

    result = ffmpeg_detect_scene_changes(input_path=input_path, threshold=threshold)
    output = f"{result.stdout}\n{result.stderr}"
    if not (result.available and result.returncode == 0):
        return _error(
            "FFMPEG_ERROR",
            "FFmpeg scene change detection failed.",
            media=str(input_path),
            ffmpeg=result.to_dict(),
        )
    changes = _parse_scene_change_output(output)
    return {
        "success": True,
        "operation": "detect_scene_changes",
        "media": str(input_path),
        "threshold": threshold,
        "scene_change_count": len(changes),
        "scene_changes": changes,
        "ffmpeg": result.to_dict(),
    }


def detect_freeze_frames(
    media: str,
    noise_db: float = -60.0,
    minimum_duration: float = 0.5,
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if noise_db >= 0:
        return _error("INVALID_ARGUMENT", "noise_db must be below 0 dB.")
    if minimum_duration <= 0:
        return _error("INVALID_ARGUMENT", "minimum_duration must be greater than zero.")
    validation_error = _validate_video_media(input_path)
    if validation_error:
        return validation_error
    validation = validate_media(str(input_path))
    media_duration = validation["media"].get("duration_seconds") if validation.get("success") else None

    result = ffmpeg_detect_freeze_frames(
        input_path=input_path,
        noise_db=noise_db,
        minimum_duration=minimum_duration,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if not (result.available and result.returncode == 0):
        return _error(
            "FFMPEG_ERROR",
            "FFmpeg freezedetect failed.",
            media=str(input_path),
            ffmpeg=result.to_dict(),
        )
    intervals = _parse_freezedetect_output(output, media_duration=media_duration)
    return {
        "success": True,
        "operation": "detect_freeze_frames",
        "media": str(input_path),
        "noise_db": noise_db,
        "minimum_duration": minimum_duration,
        "freeze_interval_count": len(intervals),
        "freeze_intervals": intervals,
        "ffmpeg": result.to_dict(),
    }


def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "ffmpeg"}


def analyze_media(
    media: str,
    include_silence: bool = True,
    include_black: bool = True,
    include_freeze: bool = True,
    include_scenes: bool = True,
    silence_threshold_db: float = -35.0,
    silence_minimum_duration: float = 0.8,
    black_minimum_duration: float = 0.5,
    freeze_minimum_duration: float = 0.5,
    scene_threshold: float = 0.35,
) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)

    validation = validate_media(str(input_path))
    if not validation.get("success"):
        return validation
    if not validation.get("valid"):
        return _error("INVALID_MEDIA", f"Media has no audio or video streams: {input_path}")

    analyses: dict[str, Any] = {}
    failure_count = 0
    if include_silence:
        if validation.get("has_audio"):
            result = audio_detect_silence(
                media=str(input_path),
                threshold_db=silence_threshold_db,
                minimum_duration=silence_minimum_duration,
            )
            analyses["silence"] = _compact_result(result)
            failure_count += 0 if result.get("success") else 1
        else:
            analyses["silence"] = {"success": True, "skipped": True, "reason": "NO_AUDIO_STREAM"}

    if include_black:
        if validation.get("has_video"):
            result = detect_black_frames(
                media=str(input_path),
                minimum_duration=black_minimum_duration,
            )
            analyses["black"] = _compact_result(result)
            failure_count += 0 if result.get("success") else 1
        else:
            analyses["black"] = {"success": True, "skipped": True, "reason": "NO_VIDEO_STREAM"}

    if include_freeze:
        if validation.get("has_video"):
            result = detect_freeze_frames(
                media=str(input_path),
                minimum_duration=freeze_minimum_duration,
            )
            analyses["freeze"] = _compact_result(result)
            failure_count += 0 if result.get("success") else 1
        else:
            analyses["freeze"] = {"success": True, "skipped": True, "reason": "NO_VIDEO_STREAM"}

    if include_scenes:
        if validation.get("has_video"):
            result = detect_scene_changes(
                media=str(input_path),
                threshold=scene_threshold,
            )
            analyses["scenes"] = _compact_result(result)
            failure_count += 0 if result.get("success") else 1
        else:
            analyses["scenes"] = {"success": True, "skipped": True, "reason": "NO_VIDEO_STREAM"}

    return {
        "success": failure_count == 0,
        "operation": "analyze_media",
        "media": str(input_path),
        "summary": {
            "has_audio": validation.get("has_audio"),
            "has_video": validation.get("has_video"),
            "duration_seconds": validation["media"].get("duration_seconds"),
            "failure_count": failure_count,
        },
        "analyses": analyses,
    }


def analyze_media_folder(
    folder: str,
    recursive: bool = True,
    max_files: int = 25,
    include_silence: bool = True,
    include_black: bool = True,
    include_freeze: bool = False,
    include_scenes: bool = True,
    silence_threshold_db: float = -35.0,
    silence_minimum_duration: float = 0.8,
    black_minimum_duration: float = 0.5,
    freeze_minimum_duration: float = 0.5,
    scene_threshold: float = 0.35,
) -> dict[str, Any]:
    if max_files < 1:
        return _error("INVALID_ARGUMENT", "max_files must be greater than zero.")
    if max_files > 500:
        return _error("INVALID_ARGUMENT", "max_files must be 500 or less.")

    scan = scan_media(folder=folder, recursive=recursive, probe=False)
    if not scan.get("success"):
        return scan

    media_items = scan.get("media", [])
    selected_items = media_items[:max_files]
    results: list[dict[str, Any]] = []
    failure_count = 0
    for item in selected_items:
        result = analyze_media(
            media=item["path"],
            include_silence=include_silence,
            include_black=include_black,
            include_freeze=include_freeze,
            include_scenes=include_scenes,
            silence_threshold_db=silence_threshold_db,
            silence_minimum_duration=silence_minimum_duration,
            black_minimum_duration=black_minimum_duration,
            freeze_minimum_duration=freeze_minimum_duration,
            scene_threshold=scene_threshold,
        )
        results.append(result)
        failure_count += 0 if result.get("success") else 1

    return {
        "success": failure_count == 0,
        "operation": "analyze_media_folder",
        "folder": scan["folder"],
        "recursive": recursive,
        "total_media_count": scan["count"],
        "analyzed_count": len(results),
        "skipped_count": max(0, scan["count"] - len(results)),
        "failure_count": failure_count,
        "results": results,
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
    "detect_black_frames": {
        "description": "Detect black video intervals using FFmpeg blackdetect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "minimum_duration": {"type": "number", "default": 0.5},
                "picture_black_ratio": {"type": "number", "default": 0.98},
                "pixel_black_threshold": {"type": "number", "default": 0.1},
            },
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": detect_black_frames,
    },
    "detect_scene_changes": {
        "description": "Detect scene change timestamps using FFmpeg scene score selection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "threshold": {"type": "number", "default": 0.35},
            },
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": detect_scene_changes,
    },
    "detect_freeze_frames": {
        "description": "Detect frozen video intervals using FFmpeg freezedetect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "noise_db": {"type": "number", "default": -60.0},
                "minimum_duration": {"type": "number", "default": 0.5},
            },
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": detect_freeze_frames,
    },
    "analyze_media": {
        "description": "Run selected read-only audio/video analyses for one media file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "include_silence": {"type": "boolean", "default": True},
                "include_black": {"type": "boolean", "default": True},
                "include_freeze": {"type": "boolean", "default": True},
                "include_scenes": {"type": "boolean", "default": True},
                "silence_threshold_db": {"type": "number", "default": -35.0},
                "silence_minimum_duration": {"type": "number", "default": 0.8},
                "black_minimum_duration": {"type": "number", "default": 0.5},
                "freeze_minimum_duration": {"type": "number", "default": 0.5},
                "scene_threshold": {"type": "number", "default": 0.35},
            },
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": analyze_media,
    },
    "analyze_media_folder": {
        "description": "Run selected read-only audio/video analyses for media files in an allowed folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
                "max_files": {"type": "integer", "default": 25},
                "include_silence": {"type": "boolean", "default": True},
                "include_black": {"type": "boolean", "default": True},
                "include_freeze": {"type": "boolean", "default": False},
                "include_scenes": {"type": "boolean", "default": True},
                "silence_threshold_db": {"type": "number", "default": -35.0},
                "silence_minimum_duration": {"type": "number", "default": 0.8},
                "black_minimum_duration": {"type": "number", "default": 0.5},
                "freeze_minimum_duration": {"type": "number", "default": 0.5},
                "scene_threshold": {"type": "number", "default": 0.35},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "handler": analyze_media_folder,
    },
}
