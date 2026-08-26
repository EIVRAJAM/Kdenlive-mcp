from __future__ import annotations

from typing import Any

from kdenlive_mcp.services.vlog_workflow_service import create_vlog_rough_cut_project, edit_timeline_and_export_project


TOOLS: dict[str, dict[str, Any]] = {
    "create_vlog_rough_cut_project": {
        "description": "Create a rough-cut .kdenlive draft from a media folder using the current safe local workflow.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "template_project": {"type": "string"},
                "output_directory": {"type": "string"},
                "name": {"type": "string", "default": "vlog_ai_001"},
                "target_duration": {"type": "number", "default": 60.0},
                "recursive": {"type": "boolean", "default": True},
                "max_files": {"type": "integer", "default": 25},
                "remove_silence": {"type": "boolean", "default": True},
                "silence_threshold_db": {"type": "number", "default": -35.0},
                "silence_minimum_duration": {"type": "number", "default": 0.8},
                "padding_before": {"type": "number", "default": 0.15},
                "padding_after": {"type": "number", "default": 0.15},
                "min_segment_duration": {"type": "number", "default": 0.25},
                "fps": {"type": "number", "default": 30.0},
                "width": {"type": "integer", "default": 1080},
                "height": {"type": "integer", "default": 1920},
                "overwrite": {"type": "boolean", "default": False},
                "check_mlt": {"type": "boolean", "default": False},
                "mlt_timeout": {"type": "number", "default": 20.0},
            },
            "required": ["folder", "template_project", "output_directory"],
            "additionalProperties": False,
        },
        "handler": create_vlog_rough_cut_project,
    },
    "edit_timeline_and_export_project": {
        "description": "Apply a batch of timeline edits and export the resulting MCP timeline to a .kdenlive draft project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeline_file": {"type": "string"},
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": ["trim", "move", "split"]},
                            "clip_id": {"type": "string"},
                            "source_in": {"type": "number"},
                            "source_out": {"type": "number"},
                            "timeline_in": {"type": "number"},
                            "split_at": {"type": "number"},
                            "include_linked": {"type": "boolean", "default": True},
                            "move_markers": {"type": "boolean", "default": True},
                        },
                        "required": ["operation", "clip_id"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                },
                "template_project": {"type": "string"},
                "output_directory": {"type": "string"},
                "name": {"type": "string", "default": "timeline_edit_ai_001"},
                "timeline_name": {"type": ["string", "null"], "default": None},
                "overwrite": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": True},
                "check_media_exists": {"type": "boolean", "default": True},
                "check_mlt": {"type": "boolean", "default": False},
                "mlt_timeout": {"type": "number", "default": 20.0},
            },
            "required": ["timeline_file", "edits", "template_project", "output_directory"],
            "additionalProperties": False,
        },
        "handler": edit_timeline_and_export_project,
    },
}
