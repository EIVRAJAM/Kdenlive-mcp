from __future__ import annotations

from typing import Any

from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.security import SecurityError, ensure_project_path


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


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
}
