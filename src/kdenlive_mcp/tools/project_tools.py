from __future__ import annotations

from typing import Any

from kdenlive_mcp.adapters.commands import run_command
from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.config import get_settings
from kdenlive_mcp.security import SecurityError, ensure_project_path
from kdenlive_mcp.services.backup_service import backup_project, clone_project
from kdenlive_mcp.services.lock_service import get_project_lock, lock_project, unlock_project
from kdenlive_mcp.services.project_workflow_service import prepare_working_project


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
