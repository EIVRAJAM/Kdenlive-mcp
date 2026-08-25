from __future__ import annotations

from typing import Any

from kdenlive_mcp.services.timeline_service import (
    create_timeline_from_rough_cut_plan,
    inspect_timeline,
    save_timeline,
    validate_timeline,
)


TOOLS: dict[str, dict[str, Any]] = {
    "create_timeline_from_rough_cut_plan": {
        "description": "Convert a persisted rough-cut plan into an MCP timeline document without writing Kdenlive XML.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan_file": {"type": "string"},
                "fps": {"type": "number", "default": 30.0},
                "width": {"type": "integer", "default": 1080},
                "height": {"type": "integer", "default": 1920},
            },
            "required": ["plan_file"],
            "additionalProperties": False,
        },
        "handler": create_timeline_from_rough_cut_plan,
    },
    "save_timeline": {
        "description": "Persist an MCP timeline document into an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeline": {"type": "object"},
                "output_directory": {"type": "string"},
                "name": {"type": "string", "default": "timeline"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["timeline", "output_directory"],
            "additionalProperties": False,
        },
        "handler": save_timeline,
    },
    "inspect_timeline": {
        "description": "Load and validate an MCP timeline document from an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {"timeline_file": {"type": "string"}},
            "required": ["timeline_file"],
            "additionalProperties": False,
        },
        "handler": inspect_timeline,
    },
    "validate_timeline": {
        "description": "Validate an MCP timeline for overlaps, duration mismatches, linked clip consistency, and media references.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeline_file": {"type": "string"},
                "check_media_exists": {"type": "boolean", "default": True},
                "duration_tolerance": {"type": "number", "default": 0.001},
            },
            "required": ["timeline_file"],
            "additionalProperties": False,
        },
        "handler": validate_timeline,
    },
}
