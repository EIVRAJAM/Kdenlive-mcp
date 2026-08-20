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


def _base_stem(stem: str) -> str:
    return re.sub(r"_(?:ai|restored)_\d{3}$", "", stem)


def _project_file_summary(path: Path, base: str) -> dict[str, Any]:
    stat = path.stat()
    version_match = re.match(rf"^{re.escape(base)}_(?P<label>[A-Za-z0-9._-]+)_(?P<index>\d{{3}})$", path.stem)
    return {
        "path": str(path),
        "filename": path.name,
        "stem": path.stem,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "label": version_match.group("label") if version_match else None,
        "index": int(version_match.group("index")) if version_match else None,
    }


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


def list_project_versions(
    project: str,
    project_directory: str | None = None,
    backup_directory: str | None = None,
) -> dict[str, Any]:
    try:
        source = ensure_project_path(project)
        directory = (
            ensure_project_path(Path(project_directory) / "__kdenlive_mcp_probe__.kdenlive").parent
            if project_directory
            else source.parent
        )
        backups_dir = ensure_output_path(backup_directory or str(directory / ".backups"))
    except SecurityError as exc:
        return _security_error(exc)

    validation_error = _validate_project_file(source)
    if validation_error:
        return validation_error

    base = _base_stem(source.stem)
    candidates = sorted(directory.glob(f"{base}*.kdenlive"))
    original: dict[str, Any] | None = None
    working_copies: list[dict[str, Any]] = []
    related_projects: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.resolve(strict=False) == source.resolve(strict=False):
            original = _project_file_summary(candidate, base)
            continue
        summary = _project_file_summary(candidate, base)
        if summary["index"] is not None:
            working_copies.append(summary)
        else:
            related_projects.append(summary)

    backup_files = sorted(backups_dir.glob(f"{base}*.kdenlive")) if backups_dir.exists() else []
    backups = [_project_file_summary(path, base) for path in backup_files]

    working_copies.sort(key=lambda item: (item["label"] or "", item["index"] or 0, item["filename"]))
    related_projects.sort(key=lambda item: item["filename"])
    backups.sort(key=lambda item: (item["mtime_ns"], item["filename"]))

    return {
        "success": True,
        "operation": "list_project_versions",
        "project": str(source),
        "base_stem": base,
        "project_directory": str(directory),
        "backup_directory": str(backups_dir),
        "original": original,
        "working_copy_count": len(working_copies),
        "backup_count": len(backups),
        "related_count": len(related_projects),
        "working_copies": working_copies,
        "backups": backups,
        "related_projects": related_projects,
    }


def restore_project_version(
    project: str,
    version: str,
    output_directory: str | None = None,
    suffix: str = "_restored",
    create_backup: bool = True,
    backup_directory: str | None = None,
) -> dict[str, Any]:
    try:
        current = ensure_project_path(project)
        source_version = ensure_project_path(version)
        destination_dir = ensure_output_path(output_directory or str(current.parent))
    except SecurityError as exc:
        return _security_error(exc)

    current_validation_error = _validate_project_file(current)
    if current_validation_error:
        return current_validation_error
    version_validation_error = _validate_project_file(source_version)
    if version_validation_error:
        return version_validation_error

    backup: dict[str, Any] | None = None
    if create_backup:
        backup_result = backup_project(
            project=str(current),
            backup_directory=backup_directory or str(destination_dir / ".backups"),
            label="before_restore",
        )
        if not backup_result.get("success"):
            return backup_result
        backup = backup_result

    restore_suffix = _slug(suffix)
    if not restore_suffix.startswith("_"):
        restore_suffix = f"_{restore_suffix}"
    destination = _next_available_path(destination_dir, f"{_base_stem(current.stem)}{restore_suffix}")
    if destination.resolve(strict=False) in {
        current.resolve(strict=False),
        source_version.resolve(strict=False),
    }:
        return _error("INVALID_OUTPUT", "Restore destination resolves to an existing source project.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_version, destination)

    restored_validation_error = _validate_project_file(destination)
    if restored_validation_error:
        return _error(
            "INVALID_RESTORE",
            "Restored project did not validate after copy.",
            validation=restored_validation_error,
        )

    return {
        "success": True,
        "operation": "restore_project_version",
        "project": str(current),
        "version": str(source_version),
        "restored_project": str(destination),
        "backup": backup["backup"] if backup else None,
        "bytes": destination.stat().st_size,
    }
