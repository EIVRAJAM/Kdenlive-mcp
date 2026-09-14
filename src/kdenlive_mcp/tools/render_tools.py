from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.commands import CommandResult, run_command
from kdenlive_mcp.adapters.ffprobe import ffprobe_json
from kdenlive_mcp.config import get_settings
from kdenlive_mcp.security import SecurityError, ensure_output_path, ensure_project_path
from kdenlive_mcp.services.manifest_service import slugify_name


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _flatpak_sandbox_error(text: str) -> bool:
    return "Unable to allocate instance id" in text


def preview_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.mp4"


def _parse_number(value: Any) -> float | None:
    if value in (None, "N/A", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probe_preview(path: Path) -> dict[str, Any] | None:
    _result, data = ffprobe_json(path)
    if data is None:
        return None
    duration = _parse_number((data.get("format") or {}).get("duration"))
    width: int | None = None
    height: int | None = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width_value = _parse_number(stream.get("width"))
            height_value = _parse_number(stream.get("height"))
            if width_value is not None and height_value is not None:
                width = int(width_value)
                height = int(height_value)
                break
    if duration is None or width is None or height is None:
        return None
    return {"duration": duration, "width": width, "height": height}


def render_preview(
    project: str,
    output_directory: str,
    name: str | None = None,
    width: int = 720,
    height: int = 1280,
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        project_path = ensure_project_path(project)
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    if not project_path.exists():
        return _error("PROJECT_NOT_FOUND", f"Project does not exist: {project_path}")
    if width <= 0 or height <= 0:
        return _error("INVALID_ARGUMENT", "width and height must be greater than zero.")

    output_path = preview_path_for(output_dir, name or f"{project_path.stem}_preview")
    if output_path.resolve(strict=False) == project_path.resolve(strict=False):
        return _error("ORIGINAL_MEDIA_PROTECTED", "Output path cannot be the original project.")
    if output_path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"Preview already exists: {output_path}")
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError as exc:
            return _error("OUTPUT_PREPARE_FAILED", f"Could not remove existing preview: {exc}")

    settings = get_settings()
    command = [
        "timeout",
        "120",
        "flatpak",
        "run",
        "--command=melt",
        settings.kdenlive_flatpak_id,
        str(project_path),
        "-consumer",
        f"avformat:{output_path}",
        f"width={width}",
        f"height={height}",
        "vcodec=libx264",
        "an=0",
        "real_time=-RT",
    ]

    start = time.perf_counter()
    result = run_command(command, timeout=150.0)
    duration_ms = (time.perf_counter() - start) * 1000

    base: dict[str, Any] = {
        "operation": "render_preview",
        "project": str(project_path),
        "output": str(output_path),
        "command_summary": command,
        "duration_ms": round(duration_ms, 3),
        "warnings": [],
    }
    output_ok = output_path.exists() and output_path.stat().st_size > 0
    if output_ok:
        render_info: dict[str, Any] = {
            "returncode": result.returncode,
            "size_bytes": output_path.stat().st_size,
        }
        probe = _probe_preview(output_path)
        if (
            probe is not None
            and probe["duration"] > 0
            and probe["width"] == width
            and probe["height"] == height
        ):
            return {
                "success": True,
                **base,
                "render": {**render_info, "probe": probe},
            }
        return {
            "success": False,
            **base,
            "error": "INVALID_RENDER_OUTPUT",
            "message": "Render preview produced an invalid output file.",
            "render": render_info,
            "probe": probe,
        }

    combined = f"{result.stdout}\n{result.stderr}\n{result.error or ''}"
    if _flatpak_sandbox_error(combined):
        return {
            "success": False,
            **base,
            "error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
            "message": "Render preview could not run Flatpak melt in this environment.",
            "warnings": [
                {
                    "code": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
                    "message": "Render preview could not run Flatpak melt in this environment.",
                }
            ],
        }

    return {
        "success": False,
        **base,
        "error": "MLT_ERROR",
        "message": "Render preview failed.",
        "render": result.to_dict(),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "render_preview": {
        "description": "Render a fast preview MP4 from a validated .kdenlive project using Flatpak melt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "output_directory": {"type": "string"},
                "name": {"type": ["string", "null"], "default": None},
                "width": {"type": "integer", "default": 720},
                "height": {"type": "integer", "default": 1280},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["project", "output_directory"],
            "additionalProperties": False,
        },
        "handler": render_preview,
    },
}
