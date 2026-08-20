from __future__ import annotations

from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.ffmpeg import extract_audio as ffmpeg_extract_audio
from kdenlive_mcp.adapters.ffmpeg import generate_thumbnail as ffmpeg_generate_thumbnail
from kdenlive_mcp.adapters.ffprobe import ffprobe_json
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path

SUPPORTED_MEDIA_EXTENSIONS = {
    ".3gp",
    ".aac",
    ".aiff",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".wav",
    ".webm",
}


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _stream_value(stream: dict[str, Any], key: str) -> Any:
    value = stream.get(key)
    return None if value in ("N/A", "") else value


def _parse_number(value: Any) -> float | None:
    if value in (None, "N/A", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _media_summary(path: Path, probe: dict[str, Any]) -> dict[str, Any]:
    streams = probe.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    fmt = probe.get("format", {})

    return {
        "path": str(path),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "duration_seconds": _parse_number(fmt.get("duration")),
        "format_name": fmt.get("format_name"),
        "bitrate": _parse_number(fmt.get("bit_rate")),
        "video": None
        if video_stream is None
        else {
            "codec": _stream_value(video_stream, "codec_name"),
            "width": _stream_value(video_stream, "width"),
            "height": _stream_value(video_stream, "height"),
            "fps": _stream_value(video_stream, "avg_frame_rate"),
            "pix_fmt": _stream_value(video_stream, "pix_fmt"),
            "rotation": video_stream.get("tags", {}).get("rotate") or _stream_value(video_stream, "rotation"),
        },
        "audio": None
        if audio_stream is None
        else {
            "codec": _stream_value(audio_stream, "codec_name"),
            "sample_rate": _stream_value(audio_stream, "sample_rate"),
            "channels": _stream_value(audio_stream, "channels"),
            "channel_layout": _stream_value(audio_stream, "channel_layout"),
        },
        "metadata": fmt.get("tags", {}),
    }


def _probe_media(path: Path) -> dict[str, Any]:
    result, data = ffprobe_json(path)
    if data is None:
        return _error("FFPROBE_ERROR", "ffprobe failed to inspect media.", ffprobe=result.to_dict())
    return {"success": True, "media": _media_summary(path, data), "ffprobe": data}


def _media_files(folder: Path, recursive: bool) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS
    )


def scan_media(folder: str, recursive: bool = True, probe: bool = True) -> dict[str, Any]:
    try:
        root = ensure_media_path(folder)
    except SecurityError as exc:
        return _security_error(exc)
    if not root.exists():
        return _error("MEDIA_NOT_FOUND", f"Folder does not exist: {root}")
    if not root.is_dir():
        return _error("INVALID_MEDIA_DIRECTORY", f"Path is not a directory: {root}")

    files = _media_files(root, recursive=recursive)
    media: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for path in files:
        if probe:
            probed = _probe_media(path)
            if probed["success"]:
                media.append(probed["media"])
            else:
                failures.append({"path": str(path), **probed})
        else:
            media.append(
                {
                    "path": str(path),
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                }
            )

    return {
        "success": True,
        "folder": str(root),
        "recursive": recursive,
        "count": len(media),
        "failure_count": len(failures),
        "media": media,
        "failures": failures,
    }


def list_media(folder: str, recursive: bool = True) -> dict[str, Any]:
    return scan_media(folder=folder, recursive=recursive, probe=False)


def get_media_info(media: str) -> dict[str, Any]:
    try:
        path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        return _error("UNSUPPORTED_MEDIA_TYPE", f"Unsupported media extension: {path.suffix}")
    return _probe_media(path)


def validate_media(media: str) -> dict[str, Any]:
    info = get_media_info(media)
    if not info.get("success"):
        return info
    streams = info["ffprobe"].get("streams", [])
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    return {
        "success": True,
        "media": info["media"],
        "valid": has_audio or has_video,
        "has_audio": has_audio,
        "has_video": has_video,
    }


def generate_thumbnail(media: str, output: str, timestamp: float = 1.0) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
        output_path = ensure_output_path(output)
    except SecurityError as exc:
        return _security_error(exc)
    if not input_path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {input_path}")
    if output_path == input_path:
        return _error("ORIGINAL_MEDIA_PROTECTED", "Output path cannot be the original media file.")
    if output_path.exists():
        return _error("OUTPUT_EXISTS", f"Output file already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = ffmpeg_generate_thumbnail(input_path, output_path, timestamp=timestamp)
    return {
        "success": result.available and result.returncode == 0 and output_path.exists(),
        "operation": "generate_thumbnail",
        "media": str(input_path),
        "output": str(output_path),
        "timestamp": timestamp,
        "ffmpeg": result.to_dict(),
    }


def extract_audio(media: str, output: str) -> dict[str, Any]:
    try:
        input_path = ensure_media_path(media)
        output_path = ensure_output_path(output)
    except SecurityError as exc:
        return _security_error(exc)
    if not input_path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {input_path}")
    if output_path == input_path:
        return _error("ORIGINAL_MEDIA_PROTECTED", "Output path cannot be the original media file.")
    if output_path.exists():
        return _error("OUTPUT_EXISTS", f"Output file already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = ffmpeg_extract_audio(input_path, output_path)
    return {
        "success": result.available and result.returncode == 0 and output_path.exists(),
        "operation": "extract_audio",
        "media": str(input_path),
        "output": str(output_path),
        "ffmpeg": result.to_dict(),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "scan_media": {
        "description": "Scan an allowed directory for media files and optionally probe metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
                "probe": {"type": "boolean", "default": True},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "handler": scan_media,
    },
    "list_media": {
        "description": "List supported media files in an allowed directory without ffprobe metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "handler": list_media,
    },
    "get_media_info": {
        "description": "Return ffprobe metadata for one allowed media file.",
        "inputSchema": {
            "type": "object",
            "properties": {"media": {"type": "string"}},
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": get_media_info,
    },
    "validate_media": {
        "description": "Validate that a media file exists, is supported, and has audio or video streams.",
        "inputSchema": {
            "type": "object",
            "properties": {"media": {"type": "string"}},
            "required": ["media"],
            "additionalProperties": False,
        },
        "handler": validate_media,
    },
    "generate_thumbnail": {
        "description": "Generate a thumbnail image from an allowed media file into an allowed output path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "output": {"type": "string"},
                "timestamp": {"type": "number", "default": 1.0},
            },
            "required": ["media", "output"],
            "additionalProperties": False,
        },
        "handler": generate_thumbnail,
    },
    "extract_audio": {
        "description": "Extract audio from an allowed media file to an allowed output WAV path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "media": {"type": "string"},
                "output": {"type": "string"},
            },
            "required": ["media", "output"],
            "additionalProperties": False,
        },
        "handler": extract_audio,
    },
}
