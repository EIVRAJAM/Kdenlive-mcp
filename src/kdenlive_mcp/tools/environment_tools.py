from __future__ import annotations

import platform
import re
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


def _version_payload(name: str, result: CommandResult, operation: str) -> dict[str, Any]:
    success = result.available and result.returncode == 0
    payload = {
        "success": success,
        "operation": operation,
        "tool": name,
        "version": _first_line(result.stdout) or _first_line(result.stderr),
        **result.to_dict(),
    }
    if not success:
        payload["message"] = result.error or f"Could not determine {name} version."
    return payload


def _flatpak_sandbox_error(result: CommandResult) -> bool:
    combined = f"{result.stdout}\n{result.stderr}\n{result.error or ''}"
    return "Unable to allocate instance id" in combined


def _flatpak_command(flatpak_id: str, inner_command: str, *args: str) -> list[str]:
    return ["flatpak", "run", f"--command={inner_command}", flatpak_id, *args]


def _flatpak_info(flatpak_id: str) -> dict[str, str]:
    result = run_command(["flatpak", "info", flatpak_id])
    if not (result.available and result.returncode == 0):
        return {}

    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip().lower()] = value.strip()
    return parsed


def _flatpak_location(flatpak_id: str) -> Path | None:
    result = run_command(["flatpak", "info", "--show-location", flatpak_id])
    if not (result.available and result.returncode == 0):
        return None
    location = result.stdout.strip()
    if not location:
        return None
    return Path(location)


def _installed_flatpak_mlt_version(flatpak_id: str) -> str | None:
    location = _flatpak_location(flatpak_id)
    if location is None:
        return None

    lib_dir = location / "files" / "lib"
    if not lib_dir.exists():
        return None

    versions: list[str] = []
    for candidate in lib_dir.glob("libmlt-7.so.*"):
        match = re.search(r"libmlt-7\.so\.(\d+\.\d+\.\d+)$", candidate.name)
        if match:
            versions.append(match.group(1))
    return sorted(versions)[-1] if versions else None


def health_check() -> dict[str, Any]:
    return {
        "success": True,
        "operation": "health_check",
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
        "operation": "get_environment",
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
    return _version_payload("ffmpeg", run_command(["ffmpeg", "-version"]), "get_ffmpeg_version")


def get_ffprobe_version() -> dict[str, Any]:
    return _version_payload("ffprobe", run_command(["ffprobe", "-version"]), "get_ffprobe_version")


def get_kdenlive_version() -> dict[str, Any]:
    settings = get_settings()
    flatpak_result = run_command(_flatpak_command(settings.kdenlive_flatpak_id, "kdenlive", "--version"))
    if flatpak_result.available and flatpak_result.returncode == 0:
        return _version_payload("kdenlive_flatpak", flatpak_result, "get_kdenlive_version")

    flatpak_info = _flatpak_info(settings.kdenlive_flatpak_id)
    if "version" in flatpak_info:
        return {
            "success": True,
            "operation": "get_kdenlive_version",
            "tool": "kdenlive_flatpak_info",
            "version": flatpak_info["version"],
            "source": "flatpak_info",
            "flatpak_id": settings.kdenlive_flatpak_id,
            "execution_available": False,
            "execution_error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
            if _flatpak_sandbox_error(flatpak_result)
            else flatpak_result.error,
            "flatpak_attempt": flatpak_result.to_dict(),
            "flatpak_info": flatpak_info,
        }

    host_result = run_command(["kdenlive", "--version"])
    payload = _version_payload("kdenlive", host_result, "get_kdenlive_version")
    payload["flatpak_attempt"] = flatpak_result.to_dict()
    payload["flatpak_info"] = flatpak_info
    return payload


def get_mlt_version() -> dict[str, Any]:
    host_result = run_command(["melt", "-version"])
    if host_result.available and host_result.returncode == 0:
        return _version_payload("melt", host_result, "get_mlt_version")

    settings = get_settings()
    flatpak_result = run_command(_flatpak_command(settings.kdenlive_flatpak_id, "melt", "-version"))
    installed_version = _installed_flatpak_mlt_version(settings.kdenlive_flatpak_id)
    if installed_version:
        return {
            "success": True,
            "operation": "get_mlt_version",
            "tool": "melt_flatpak_installation",
            "version": f"melt {installed_version}",
            "mlt_version": installed_version,
            "source": "flatpak_installation_scan",
            "flatpak_id": settings.kdenlive_flatpak_id,
            "execution_available": False,
            "execution_error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
            if _flatpak_sandbox_error(flatpak_result)
            else flatpak_result.error,
            "host_attempt": host_result.to_dict(),
            "flatpak_attempt": flatpak_result.to_dict(),
        }

    payload = _version_payload("melt_flatpak", flatpak_result, "get_mlt_version")
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
