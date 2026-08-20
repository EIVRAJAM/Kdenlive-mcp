from __future__ import annotations

from typing import Any

from kdenlive_mcp.services.manifest_service import (
    create_manifest,
    inspect_manifest,
    scan_media_to_manifest,
    validate_manifest,
)


TOOLS: dict[str, dict[str, Any]] = {
    "create_manifest": {
        "description": "Create a non-Kdenlive JSON project manifest in an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "output_directory": {"type": "string"},
                "description": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["name", "output_directory"],
            "additionalProperties": False,
        },
        "handler": create_manifest,
    },
    "inspect_manifest": {
        "description": "Load and return one MCP project manifest.",
        "inputSchema": {
            "type": "object",
            "properties": {"manifest": {"type": "string"}},
            "required": ["manifest"],
            "additionalProperties": False,
        },
        "handler": inspect_manifest,
    },
    "validate_manifest": {
        "description": "Validate manifest JSON structure and referenced media file existence.",
        "inputSchema": {
            "type": "object",
            "properties": {"manifest": {"type": "string"}},
            "required": ["manifest"],
            "additionalProperties": False,
        },
        "handler": validate_manifest,
    },
    "scan_media_to_manifest": {
        "description": "Scan an allowed media folder and store the results in an MCP project manifest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest": {"type": "string"},
                "folder": {"type": "string"},
                "recursive": {"type": "boolean", "default": True},
                "replace": {"type": "boolean", "default": True},
            },
            "required": ["manifest", "folder"],
            "additionalProperties": False,
        },
        "handler": scan_media_to_manifest,
    },
}
