from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from kdenlive_mcp import __version__
from kdenlive_mcp.adapters.commands import CommandResult, binary_exists, run_command
from kdenlive_mcp.config import get_settings


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _version_payload(name: str, result: CommandResult) -> dict[str, Any]:
    return {
        "success": result.available and result.returncode == 0,
        "tool": name,
        "version": _first_line(result.stdout) or _first_line(result.stderr),
        **result.to_dict(),
    }


def _flatpak_command(flatpak_id: str, inner_command: str, *args: str) -> list[str]:
    return ["flatpak", "run", f"--command={inner_command}", flatpak_id, *args]


def health_check() -> dict[str, Any]:
    return {
        "success": True,
        "service": "kdenlive-mcp",
        "version": __version__,
        "status": "ok",
        "capabilities": [
            "environment_detection",
            "version_detection",
            "mcp_stdio_jsonrpc",
        ],
    }


def get_environment() -> dict[str, Any]:
    settings = get_settings()
    binaries = {
        "python3": binary_exists("python3"),
        "ffmpeg": binary_exists("ffmpeg"),
        "ffprobe": binary_exists("ffprobe"),
        "flatpak": binary_exists("flatpak"),
        "melt": binary_exists("melt"),
        "kdenlive": binary_exists("kdenlive"),
    }
    return {
        "success": True,
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cwd": str(Path.cwd()),
        "binaries": binaries,
        "settings": {
            "allowed_media_directories": [str(path) for path in settings.allowed_media_directories],
            "allowed_project_directories": [str(path) for path in settings.allowed_project_directories],
            "allowed_output_directories": [str(path) for path in settings.allowed_output_directories],
            "kdenlive_flatpak_id": settings.kdenlive_flatpak_id,
        },
    }


def get_ffmpeg_version() -> dict[str, Any]:
    return _version_payload("ffmpeg", run_command(["ffmpeg", "-version"]))


def get_ffprobe_version() -> dict[str, Any]:
    return _version_payload("ffprobe", run_command(["ffprobe", "-version"]))


def get_kdenlive_version() -> dict[str, Any]:
    settings = get_settings()
    flatpak_result = run_command(_flatpak_command(settings.kdenlive_flatpak_id, "kdenlive", "--version"))
    if flatpak_result.available and flatpak_result.returncode == 0:
        return _version_payload("kdenlive_flatpak", flatpak_result)
    host_result = run_command(["kdenlive", "--version"])
    payload = _version_payload("kdenlive", host_result)
    payload["flatpak_attempt"] = flatpak_result.to_dict()
    return payload


def get_mlt_version() -> dict[str, Any]:
    host_result = run_command(["melt", "-version"])
    if host_result.available and host_result.returncode == 0:
        return _version_payload("melt", host_result)

    settings = get_settings()
    flatpak_result = run_command(_flatpak_command(settings.kdenlive_flatpak_id, "melt", "-version"))
    payload = _version_payload("melt_flatpak", flatpak_result)
    payload["host_attempt"] = host_result.to_dict()
    return payload


TOOLS: dict[str, dict[str, Any]] = {
    "health_check": {
        "description": "Return server health and basic capabilities.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": health_check,
    },
    "get_environment": {
        "description": "Return Python, platform, binary, and allowlist configuration details.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": get_environment,
    },
    "get_kdenlive_version": {
        "description": "Return Kdenlive version, preferring the configured Flatpak.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": get_kdenlive_version,
    },
    "get_ffmpeg_version": {
        "description": "Return host FFmpeg version.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": get_ffmpeg_version,
    },
    "get_ffprobe_version": {
        "description": "Return host ffprobe version.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": get_ffprobe_version,
    },
    "get_mlt_version": {
        "description": "Return MLT melt version, preferring host melt then Kdenlive Flatpak melt.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": get_mlt_version,
    },
}
