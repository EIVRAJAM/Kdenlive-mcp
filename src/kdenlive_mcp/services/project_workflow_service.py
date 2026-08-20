from __future__ import annotations

from pathlib import Path
from typing import Any

from kdenlive_mcp.security import SecurityError, ensure_project_path
from kdenlive_mcp.services.backup_service import clone_project
from kdenlive_mcp.services.lock_service import lock_project


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def prepare_working_project(
    project: str,
    output_directory: str | None = None,
    suffix: str = "_ai",
    owner: str = "codex",
    create_backup: bool = True,
    backup_directory: str | None = None,
    lock_directory: str | None = None,
) -> dict[str, Any]:
    if output_directory is not None:
        try:
            ensure_project_path(Path(output_directory) / "__kdenlive_mcp_permission_probe__.kdenlive")
        except SecurityError as exc:
            return _error(exc.code, exc.message)

    clone = clone_project(
        project=project,
        output_directory=output_directory,
        suffix=suffix,
        create_backup=create_backup,
        backup_directory=backup_directory,
    )
    if not clone.get("success"):
        return clone

    lock = lock_project(
        project=clone["clone"],
        owner=owner,
        lock_directory=lock_directory,
    )
    if not lock.get("success"):
        return _error(
            "PROJECT_LOCK_FAILED",
            "Working project was cloned but could not be locked.",
            clone=clone,
            lock=lock,
        )

    return {
        "success": True,
        "operation": "prepare_working_project",
        "project": clone["project"],
        "working_project": clone["clone"],
        "backup": clone["backup"],
        "lock_file": lock["lock_file"],
        "owner": owner,
        "clone": clone,
        "lock": lock,
    }
