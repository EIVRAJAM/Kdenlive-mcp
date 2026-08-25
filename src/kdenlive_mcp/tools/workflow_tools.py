from __future__ import annotations

from typing import Any

from kdenlive_mcp.services.vlog_workflow_service import create_vlog_rough_cut_project


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
            },
            "required": ["folder", "template_project", "output_directory"],
            "additionalProperties": False,
        },
        "handler": create_vlog_rough_cut_project,
    },
}
