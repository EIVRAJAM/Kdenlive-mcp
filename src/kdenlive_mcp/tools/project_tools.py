from __future__ import annotations

from typing import Any

from kdenlive_mcp.adapters.commands import run_command
from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.config import get_settings
from kdenlive_mcp.security import SecurityError, ensure_output_path, ensure_project_path
from kdenlive_mcp.services.backup_service import (
    backup_project,
    clone_project,
    list_project_versions,
    restore_project_version,
)
from kdenlive_mcp.services.lock_service import get_project_lock, lock_project, unlock_project
from kdenlive_mcp.services.project_workflow_service import prepare_working_project
from kdenlive_mcp.services.timeline_service import save_timeline


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _flatpak_sandbox_error(text: str) -> bool:
    return "Unable to allocate instance id" in text


def inspect_project(project: str) -> dict[str, Any]:
    try:
        path = ensure_project_path(project)
        data = KdenliveProjectAdapter().inspect(path)
    except SecurityError as exc:
        return _error(exc.code, exc.message)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)
    return {
        "success": True,
        "operation": "inspect_project",
        "project": str(path),
        "data": data,
    }


def inspect_kdenlive_timeline(project: str) -> dict[str, Any]:
    try:
        path = ensure_project_path(project)
    except SecurityError as exc:
        return _error(exc.code, exc.message)
    if not path.exists():
        return _error("PROJECT_NOT_FOUND", f"Project does not exist: {path}")
    try:
        summary = KdenliveProjectAdapter().extract_timeline_summary(path)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)

    warnings: list[dict[str, str]] = []
    if summary.get("inferred_fields"):
        warnings.append(
            {
                "code": "TIMELINE_SUMMARY_HAS_INFERRED_FIELDS",
                "message": "Some timeline fields are inferred from Kdenlive XML structure and should not be treated as authoritative edit targets yet.",
            }
        )
    return {
        "success": True,
        "operation": "inspect_kdenlive_timeline",
        "project": str(path),
        "summary": summary,
        "warnings": warnings,
    }


def export_kdenlive_timeline(
    project: str,
    output_directory: str,
    name: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        path = ensure_project_path(project)
    except SecurityError as exc:
        return _error(exc.code, exc.message)
    if not path.exists():
        return _error("PROJECT_NOT_FOUND", f"Project does not exist: {path}")
    try:
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _error(exc.code, exc.message)
    try:
        document = KdenliveProjectAdapter().extract_timeline_document(path)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)

    output_dir.mkdir(parents=True, exist_ok=True)
    timeline_dict = document.model_dump(mode="json", exclude_none=True)
    saved = save_timeline(
        timeline=timeline_dict,
        output_directory=str(output_dir),
        name=name or path.stem,
        overwrite=overwrite,
    )
    if not saved.get("success"):
        return {**saved, "operation": "export_kdenlive_timeline"}
    return {
        "success": True,
        "operation": "export_kdenlive_timeline",
        "project": str(path),
        "timeline_file": saved["timeline_file"],
        "timeline": timeline_dict,
        "warnings": [
            {
                "code": "TIMELINE_EXPORTED_FROM_KDENLIVE",
                "message": "TimelineDocument was exported from the project's current Kdenlive timeline using the supported reverse-adapter subset.",
            }
        ],
    }


def validate_project(
    project: str,
    check_mlt: bool = False,
    timeout: float = 20.0,
) -> dict[str, Any]:
    try:
        path = ensure_project_path(project)
        data = KdenliveProjectAdapter().inspect(path)
    except SecurityError as exc:
        return _error(exc.code, exc.message)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)

    static_valid = data["validation"]["well_formed_xml"] and data["validation"]["missing_media_count"] == 0
    checks: dict[str, Any] = {
        "xml_parse": {"checked": True, "valid": True},
        "media_references": {
            "checked": True,
            "valid": data["validation"]["missing_media_count"] == 0,
            "missing_media_count": data["validation"]["missing_media_count"],
            "missing_media": data["validation"]["missing_media"],
        },
        "mlt_load": {"checked": False, "valid": None},
    }

    mlt_affects_validity = False
    if check_mlt:
        settings = get_settings()
        result = run_command(
            [
                "flatpak",
                "run",
                "--command=melt",
                settings.kdenlive_flatpak_id,
                str(path),
                "-consumer",
                "null",
                "terminate_on_pause=1",
            ],
            timeout=timeout,
        )
        combined_output = f"{result.stdout}\n{result.stderr}\n{result.error or ''}"
        if result.available and result.returncode == 0:
            checks["mlt_load"] = {
                "checked": True,
                "valid": True,
                "status": "loaded",
                "command": result.command,
                "returncode": result.returncode,
            }
            mlt_affects_validity = True
        elif _flatpak_sandbox_error(combined_output):
            checks["mlt_load"] = {
                "checked": True,
                "valid": None,
                "status": "unavailable",
                "error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
                "command": result.command,
                "returncode": result.returncode,
            }
        else:
            checks["mlt_load"] = {
                "checked": True,
                "valid": False,
                "status": "failed",
                "error": result.error,
                "command": result.command,
                "returncode": result.returncode,
                "stderr": result.stderr,
            }
            mlt_affects_validity = True

    mlt_valid = checks["mlt_load"]["valid"] is not False if mlt_affects_validity else True
    valid = static_valid and mlt_valid
    return {
        "success": True,
        "operation": "validate_project",
        "project": str(path),
        "valid": bool(valid),
        "checks": checks,
        "summary": {
            "profile": data["document"]["profile"],
            "kdenlive_version": data["document"]["kdenlive_version"],
            "media_count": data["bin"]["media_count"],
            "sequence_count": len(data["sequences"]),
            "missing_media_count": data["validation"]["missing_media_count"],
        },
    }


TOOLS: dict[str, dict[str, Any]] = {
    "inspect_project": {
        "description": "Read a .kdenlive project and return a structured, read-only summary.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": inspect_project,
    },
    "inspect_kdenlive_timeline": {
        "description": "Read-only Kdenlive timeline summary of a .kdenlive project (no writes, no conversion).",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": inspect_kdenlive_timeline,
    },
    "export_kdenlive_timeline": {
        "description": "Convert a simple .kdenlive project to a TimelineDocument (reverse adapter subset) and save it as .timeline.json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "output_directory": {"type": "string"},
                "name": {"type": ["string", "null"], "default": None},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["project", "output_directory"],
            "additionalProperties": False,
        },
        "handler": export_kdenlive_timeline,
    },
    "validate_project": {
        "description": "Validate a .kdenlive project without modifying it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "check_mlt": {"type": "boolean", "default": False},
                "timeout": {"type": "number", "default": 20.0},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": validate_project,
    },
    "backup_project": {
        "description": "Create a timestamped copy of a validated .kdenlive project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "backup_directory": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": backup_project,
    },
    "clone_project": {
        "description": "Create the next non-destructive AI working copy of a validated .kdenlive project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "output_directory": {"type": "string"},
                "suffix": {"type": "string", "default": "_ai"},
                "create_backup": {"type": "boolean", "default": True},
                "backup_directory": {"type": "string"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": clone_project,
    },
    "list_project_versions": {
        "description": "List related .kdenlive working copies and backups for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "project_directory": {"type": "string"},
                "backup_directory": {"type": "string"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": list_project_versions,
    },
    "restore_project_version": {
        "description": "Copy a selected .kdenlive version into a new restored project file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "version": {"type": "string"},
                "output_directory": {"type": "string"},
                "suffix": {"type": "string", "default": "_restored"},
                "create_backup": {"type": "boolean", "default": True},
                "backup_directory": {"type": "string"},
            },
            "required": ["project", "version"],
            "additionalProperties": False,
        },
        "handler": restore_project_version,
    },
    "get_project_lock": {
        "description": "Return lock status for a .kdenlive project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "lock_directory": {"type": "string"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": get_project_lock,
    },
    "lock_project": {
        "description": "Create an owner-scoped lock for a .kdenlive project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "owner": {"type": "string", "default": "codex"},
                "lock_directory": {"type": "string"},
                "stale_after_seconds": {"type": "integer"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": lock_project,
    },
    "unlock_project": {
        "description": "Release an owner-scoped lock for a .kdenlive project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "owner": {"type": "string", "default": "codex"},
                "lock_directory": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": unlock_project,
    },
    "prepare_working_project": {
        "description": "Clone a .kdenlive project to an AI working copy and lock the clone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "output_directory": {"type": "string"},
                "suffix": {"type": "string", "default": "_ai"},
                "owner": {"type": "string", "default": "codex"},
                "create_backup": {"type": "boolean", "default": True},
                "backup_directory": {"type": "string"},
                "lock_directory": {"type": "string"},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        "handler": prepare_working_project,
    },
}
