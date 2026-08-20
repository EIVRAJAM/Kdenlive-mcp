from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.security import SecurityError, ensure_output_path, ensure_project_path


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _validate_project_file(path: Path) -> dict[str, Any] | None:
    try:
        data = KdenliveProjectAdapter().inspect(path)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)
    if data["validation"]["missing_media_count"]:
        return _error(
            "MEDIA_OFFLINE",
            "Project has missing media references.",
            missing_media=data["validation"]["missing_media"],
        )
    return None


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "backup"


def _next_available_path(directory: Path, stem: str, suffix: str = ".kdenlive") -> Path:
    index = 1
    while True:
        candidate = directory / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def backup_project(
    project: str,
    backup_directory: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    try:
        source = ensure_project_path(project)
        destination_dir = ensure_output_path(backup_directory or str(source.parent / ".backups"))
    except SecurityError as exc:
        return _security_error(exc)

    validation_error = _validate_project_file(source)
    if validation_error:
        return validation_error

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label_part = f"_{_slug(label)}" if label else ""
    stem = f"{source.stem}{label_part}_{timestamp}"
    destination = _next_available_path(destination_dir, stem)
    if destination.resolve(strict=False) == source.resolve(strict=False):
        return _error("INVALID_OUTPUT", "Backup destination resolves to the source project.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    return {
        "success": True,
        "operation": "backup_project",
        "project": str(source),
        "backup": str(destination),
        "bytes": destination.stat().st_size,
    }


def clone_project(
    project: str,
    output_directory: str | None = None,
    suffix: str = "_ai",
    create_backup: bool = True,
    backup_directory: str | None = None,
) -> dict[str, Any]:
    try:
        source = ensure_project_path(project)
        destination_dir = ensure_output_path(output_directory or str(source.parent))
    except SecurityError as exc:
        return _security_error(exc)

    validation_error = _validate_project_file(source)
    if validation_error:
        return validation_error

    backup: dict[str, Any] | None = None
    if create_backup:
        backup_result = backup_project(
            project=str(source),
            backup_directory=backup_directory or str(destination_dir / ".backups"),
            label="before_clone",
        )
        if not backup_result.get("success"):
            return backup_result
        backup = backup_result

    version_suffix = _slug(suffix)
    if not version_suffix.startswith("_"):
        version_suffix = f"_{version_suffix}"
    destination = _next_available_path(destination_dir, f"{source.stem}{version_suffix}")
    if destination.resolve(strict=False) == source.resolve(strict=False):
        return _error("INVALID_OUTPUT", "Clone destination resolves to the source project.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    clone_validation_error = _validate_project_file(destination)
    if clone_validation_error:
        return _error(
            "INVALID_CLONE",
            "Cloned project did not validate after copy.",
            validation=clone_validation_error,
        )

    return {
        "success": True,
        "operation": "clone_project",
        "project": str(source),
        "clone": str(destination),
        "backup": backup["backup"] if backup else None,
        "bytes": destination.stat().st_size,
    }
