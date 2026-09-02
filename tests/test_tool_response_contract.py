from __future__ import annotations

import json
from pathlib import Path

from kdenlive_mcp import server
from kdenlive_mcp.server import handle_request
from kdenlive_mcp.tools import environment_tools


SUCCESS_TOOLS = [
    "health_check",
    "get_environment",
    "get_ffmpeg_version",
    "get_ffprobe_version",
    "get_mlt_version",
    "get_kdenlive_version",
]

ERROR_CASES = [
    ("inspect_manifest", {"manifest": "nope.json"}, "MANIFEST_NOT_FOUND"),
    ("inspect_timeline", {"timeline_file": "nope.timeline.json"}, "TIMELINE_NOT_FOUND"),
    ("inspect_project", {"project": "nope.kdenlive"}, "PROJECT_NOT_FOUND"),
    ("get_media_info", {"media": "nope.mp4"}, "MEDIA_NOT_FOUND"),
    ("inspect_rough_cut_plan", {"plan_file": "nope.json"}, "ROUGH_CUT_PLAN_NOT_FOUND"),
]


def _call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "audit",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    return json.loads(response["result"]["content"][0]["text"])


def _assert_contract(payload: dict[str, object]) -> None:
    assert isinstance(payload["success"], bool)
    assert isinstance(payload["operation"], str) and payload["operation"]
    if payload["success"] is False:
        assert isinstance(payload["error"], str) and payload["error"]
        assert isinstance(payload["message"], str) and payload["message"]


def _assert_mcp_contract(payload: dict[str, object]) -> None:
    _assert_contract(payload)
    assert isinstance(payload["warnings"], list)


def test_all_tool_definitions_declare_object_schema_and_handler() -> None:
    for name, definition in server.TOOLS.items():
        assert definition["inputSchema"]["type"] == "object"
        assert callable(definition["handler"])
        assert isinstance(definition["description"], str) and definition["description"]


def test_cheap_tool_success_responses_meet_contract(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")

    for name in SUCCESS_TOOLS:
        payload = _call_tool(name, {})
        assert payload["operation"] == name
        _assert_mcp_contract(payload)


def test_controlled_error_responses_meet_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    for name, arguments, expected_error in ERROR_CASES:
        payload = _call_tool(name, {key: str(tmp_path / value) for key, value in arguments.items()})
        assert payload["success"] is False
        assert payload["error"] == expected_error
        assert payload["operation"] == name
        _assert_mcp_contract(payload)


def test_environment_handlers_include_operation_directly() -> None:
    for name in ("health_check", "get_environment"):
        payload = server.TOOLS[name]["handler"]()
        assert payload["operation"] == name
        _assert_contract(payload)


def test_version_tool_failure_includes_error_message_and_operation(monkeypatch) -> None:
    monkeypatch.setattr(
        environment_tools,
        "run_command",
        lambda command: environment_tools.CommandResult(
            command=command,
            available=False,
            returncode=None,
            stdout="",
            stderr="",
            error="Executable not found: ffmpeg",
        ),
    )

    payload = environment_tools.get_ffmpeg_version()

    assert payload["success"] is False
    assert payload["operation"] == "get_ffmpeg_version"
    assert payload["error"] == "Executable not found: ffmpeg"
    assert payload["message"] == "Executable not found: ffmpeg"


def test_mcp_boundary_guarantees_success_for_malformed_responses(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    monkeypatch.setitem(
        server.TOOLS,
        "malformed_tool",
        {
            "description": "Tool returning a malformed response for boundary tests.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "handler": lambda **kwargs: "not-a-dict",
        },
    )

    payload = _call_tool("malformed_tool", {})

    _assert_mcp_contract(payload)
    assert payload["success"] is False
    assert payload["error"] == "INVALID_TOOL_RESPONSE"
    assert payload["operation"] == "malformed_tool"


def test_mcp_boundary_rejects_unsupported_schema_version(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    timeline = tmp_path / "future.timeline.json"
    timeline.write_text(json.dumps({"kind": "kdenlive_mcp_timeline", "schema_version": 2}), encoding="utf-8")

    payload = _call_tool("inspect_timeline", {"timeline_file": str(timeline)})

    _assert_mcp_contract(payload)
    assert payload["success"] is False
    assert payload["error"] == "UNSUPPORTED_SCHEMA_VERSION"
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["operation"] == "inspect_timeline"


def test_mcp_boundary_maps_non_object_timeline_root_to_invalid_timeline(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    timeline = tmp_path / "array.timeline.json"
    timeline.write_text("[]", encoding="utf-8")

    payload = _call_tool("inspect_timeline", {"timeline_file": str(timeline)})

    _assert_mcp_contract(payload)
    assert payload["success"] is False
    assert payload["error"] == "INVALID_TIMELINE"
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["operation"] == "inspect_timeline"
