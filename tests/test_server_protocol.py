from __future__ import annotations

import io
import json

import pytest

from kdenlive_mcp.server import McpError, _error_response, handle_request, read_message, write_message
from kdenlive_mcp import server
from kdenlive_mcp.logging import append_tool_log


def _framed(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _raise_value_error(**kwargs: object) -> dict[str, object]:
    raise ValueError("boom")


def _exploding_tool_entry() -> dict[str, object]:
    return {
        "description": "Tool that raises for MCP boundary tests.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": _raise_value_error,
    }


def _required_arg_tool(required_arg: str) -> dict[str, object]:
    return {"success": True, "required_arg": required_arg}


def _required_arg_tool_entry() -> dict[str, object]:
    return {
        "description": "Tool with a required argument for binding tests.",
        "inputSchema": {
            "type": "object",
            "properties": {"required_arg": {"type": "string"}},
            "required": ["required_arg"],
        },
        "handler": _required_arg_tool,
    }


def _internal_type_error_tool(**kwargs: object) -> dict[str, object]:
    raise TypeError("internal boom")


def _internal_type_error_tool_entry() -> dict[str, object]:
    return {
        "description": "Tool that raises TypeError internally for classification tests.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": _internal_type_error_tool,
    }


def _schema_tool(
    *,
    folder: str,
    level: int = 0,
    tags: list[str] | None = None,
    mode: str = "normal",
    output: str | None = None,
) -> dict[str, object]:
    return {"success": True, "folder": folder}


def _schema_tool_entry() -> dict[str, object]:
    return {
        "description": "Tool with a rich schema for argument validation tests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "level": {"type": "integer", "default": 0},
                "tags": {"type": "array", "items": {"type": "string"}, "default": None},
                "mode": {"type": "string", "enum": ["normal", "fast"], "default": "normal"},
                "output": {"type": ["string", "null"], "default": None},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "handler": _schema_tool,
    }


def _number_tool(*, value: float) -> dict[str, object]:
    return {"success": True, "value": value}


def _number_tool_entry() -> dict[str, object]:
    return {
        "description": "Tool with a single numeric argument for finite-number tests.",
        "inputSchema": {
            "type": "object",
            "properties": {"value": {"type": "number"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        "handler": _number_tool,
    }


def test_read_and_write_mcp_message() -> None:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    stream = io.BytesIO(_framed(payload))

    assert read_message(stream) == payload

    output = io.BytesIO()
    write_message(output, {"jsonrpc": "2.0", "id": 1, "result": {}})

    assert output.getvalue().startswith(b"Content-Length: ")
    assert b'\r\n\r\n{"jsonrpc":"2.0","id":1,"result":{}}' in output.getvalue()


def test_initialize_response() -> None:
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    assert response is not None
    assert response["result"]["serverInfo"]["name"] == "kdenlive-mcp"
    assert "tools" in response["result"]["capabilities"]


def test_tools_list_includes_health_check() -> None:
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    assert response is not None
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert "health_check" in tool_names
    assert "scan_media" in tool_names
    assert "detect_silence" in tool_names
    assert "plan_silence_removal" in tool_names
    assert "extract_frames" in tool_names
    assert "generate_contact_sheet" in tool_names
    assert "detect_black_frames" in tool_names
    assert "detect_scene_changes" in tool_names
    assert "detect_freeze_frames" in tool_names
    assert "analyze_media" in tool_names
    assert "analyze_media_folder" in tool_names
    assert "plan_rough_cut" in tool_names
    assert "save_rough_cut_plan" in tool_names
    assert "inspect_rough_cut_plan" in tool_names
    assert "create_rough_cut_plan_file" in tool_names
    assert "create_timeline_from_rough_cut_plan" in tool_names
    assert "save_timeline" in tool_names
    assert "inspect_timeline" in tool_names
    assert "validate_timeline" in tool_names
    assert "create_timeline_track" in tool_names
    assert "update_timeline_track" in tool_names
    assert "remove_timeline_track" in tool_names
    assert "add_timeline_clip" in tool_names
    assert "remove_timeline_clip" in tool_names
    assert "duplicate_timeline_clip" in tool_names
    assert "insert_timeline_gap" in tool_names
    assert "remove_timeline_gap" in tool_names
    assert "trim_timeline_clip" in tool_names
    assert "move_timeline_clip" in tool_names
    assert "split_timeline_clip" in tool_names
    assert "apply_timeline_edits" in tool_names
    assert "export_timeline_to_mlt_xml" in tool_names
    assert "export_timeline_to_kdenlive_template" in tool_names
    assert "create_vlog_rough_cut_project" in tool_names
    assert "edit_timeline_and_export_project" in tool_names
    assert "create_manifest" in tool_names
    assert "inspect_project" in tool_names
    assert "validate_project" in tool_names
    assert "backup_project" in tool_names
    assert "clone_project" in tool_names
    assert "list_project_versions" in tool_names
    assert "restore_project_version" in tool_names
    assert "get_project_lock" in tool_names
    assert "lock_project" in tool_names
    assert "unlock_project" in tool_names
    assert "prepare_working_project" in tool_names


def test_tools_call_health_check() -> None:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "health_check", "arguments": {}},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert json.loads(text)["success"] is True


def test_tools_call_writes_structured_log(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "kdenlive-mcp.log"
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", str(log_file))

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "log-test",
            "method": "tools/call",
            "params": {"name": "health_check", "arguments": {}},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "tool_call"
    assert records[0]["request_id"] == "log-test"
    assert records[0]["operation"] == "health_check"
    assert records[0]["success"] is True
    assert records[0]["arguments"] == {}
    assert isinstance(records[0]["duration_ms"], float)


def test_structured_log_redacts_sensitive_arguments(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "redacted.log"
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", str(log_file))

    append_tool_log(
        request_id=1,
        tool_name="example",
        arguments={"api_key": "secret-value", "nested": {"password": "hidden", "name": "kept"}},
        result={"success": False, "error": "EXAMPLE_ERROR"},
        duration_ms=1.25,
    )

    record = json.loads(log_file.read_text(encoding="utf-8"))
    assert record["arguments"] == {
        "api_key": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "name": "kept"},
    }
    assert record["error"] == "EXAMPLE_ERROR"


def test_tools_call_logging_can_be_disabled(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "disabled.log"
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "log-disabled",
            "method": "tools/call",
            "params": {"name": "health_check", "arguments": {}},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False
    assert not log_file.exists()


def test_tools_call_wraps_unexpected_exception(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "exploding_tool", _exploding_tool_entry())

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "boom",
            "method": "tools/call",
            "params": {"name": "exploding_tool", "arguments": {}},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is False
    assert payload["error"] == "INTERNAL_ERROR"
    assert payload["message"] == "Tool execution failed unexpectedly."
    assert payload["operation"] == "exploding_tool"
    assert "traceback" not in payload


def test_tools_list_unaffected_by_handler_exception(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "exploding_tool", _exploding_tool_entry())
    handle_request(
        {
            "jsonrpc": "2.0",
            "id": "boom",
            "method": "tools/call",
            "params": {"name": "exploding_tool", "arguments": {}},
        }
    )

    response = handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})

    assert response is not None
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert "health_check" in tool_names
    assert "exploding_tool" in tool_names


def test_tools_call_logs_unexpected_exception(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "kdenlive-mcp-error.log"
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", str(log_file))
    monkeypatch.setitem(server.TOOLS, "exploding_tool", _exploding_tool_entry())

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "boom-log",
            "method": "tools/call",
            "params": {"name": "exploding_tool", "arguments": {}},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "tool_call"
    assert records[0]["request_id"] == "boom-log"
    assert records[0]["operation"] == "exploding_tool"
    assert records[0]["success"] is False
    assert records[0]["error"] == "INTERNAL_ERROR"
    assert records[0]["error_type"] == "ValueError"
    assert records[0]["message"] == "boom"


def test_tools_call_reports_missing_argument_as_jsonrpc_error(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "required_arg_tool", _required_arg_tool_entry())

    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "bind-error",
                "method": "tools/call",
                "params": {"name": "required_arg_tool", "arguments": {}},
            }
        )

    response = _error_response("bind-error", excinfo.value)
    assert excinfo.value.code == -32602
    assert excinfo.value.message.startswith("Invalid arguments for required_arg_tool")
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "bind-error"
    assert response["error"]["code"] == -32602
    assert response["error"]["message"].startswith("Invalid arguments for required_arg_tool")


def test_tools_call_internal_type_error_is_not_argument_error(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "internal_type_error_tool", _internal_type_error_tool_entry())

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "boom-type",
            "method": "tools/call",
            "params": {"name": "internal_type_error_tool", "arguments": {}},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is False
    assert payload["error"] == "INTERNAL_ERROR"
    assert payload["message"] == "Tool execution failed unexpectedly."
    assert payload["operation"] == "internal_type_error_tool"
    assert "traceback" not in payload


def test_tools_call_logs_internal_type_error(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "kdenlive-mcp-typeerror.log"
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", str(log_file))
    monkeypatch.setitem(server.TOOLS, "internal_type_error_tool", _internal_type_error_tool_entry())

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "boom-type-log",
            "method": "tools/call",
            "params": {"name": "internal_type_error_tool", "arguments": {}},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["success"] is False
    assert records[0]["error"] == "INTERNAL_ERROR"
    assert records[0]["error_type"] == "TypeError"
    assert records[0]["message"] == "internal boom"


@pytest.mark.parametrize("bad_arguments", [[], "", 0, False])
def test_tools_call_rejects_non_object_arguments(monkeypatch, bad_arguments) -> None:
    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "bad-args",
                "method": "tools/call",
                "params": {"name": "health_check", "arguments": bad_arguments},
            }
        )
    assert excinfo.value.code == -32602
    assert excinfo.value.message == "Tool arguments must be an object"


def test_tools_call_accepts_none_arguments_as_empty() -> None:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "none-args",
            "method": "tools/call",
            "params": {"name": "health_check", "arguments": None},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False


def _call_schema_tool(arguments: dict[str, object]) -> dict[str, object]:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "schema-tool",
            "method": "tools/call",
            "params": {"name": "schema_tool", "arguments": arguments},
        }
    )
    assert response is not None
    return response


def test_schema_rejects_missing_required_field(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    with pytest.raises(McpError) as excinfo:
        _call_schema_tool({})
    assert excinfo.value.code == -32602
    assert "missing required property 'folder'" in excinfo.value.message


def test_schema_rejects_unexpected_property(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    with pytest.raises(McpError) as excinfo:
        _call_schema_tool({"folder": "x", "bogus": 1})
    assert excinfo.value.code == -32602
    assert "unexpected property 'bogus'" in excinfo.value.message


def test_schema_rejects_wrong_type(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    with pytest.raises(McpError) as excinfo:
        _call_schema_tool({"folder": 42})
    assert excinfo.value.code == -32602
    assert "'folder' must be of type" in excinfo.value.message


def test_schema_rejects_invalid_enum(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    with pytest.raises(McpError) as excinfo:
        _call_schema_tool({"folder": "x", "mode": "turbo"})
    assert excinfo.value.code == -32602
    assert "'mode' must be one of" in excinfo.value.message


def test_schema_rejects_array_with_non_string_item(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    with pytest.raises(McpError) as excinfo:
        _call_schema_tool({"folder": "x", "tags": [1]})
    assert excinfo.value.code == -32602
    assert "'tags[0]' must be of type" in excinfo.value.message


def test_schema_accepts_valid_arguments(monkeypatch) -> None:
    monkeypatch.setitem(server.TOOLS, "schema_tool", _schema_tool_entry())

    response = _call_schema_tool({"folder": "x", "mode": "fast", "tags": ["a"], "level": 2, "output": None})

    assert response["result"]["isError"] is False
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["success"] is True
    assert payload["folder"] == "x"


def test_move_timeline_clip_missing_timeline_in_fails_schema() -> None:
    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "real-tool",
                "method": "tools/call",
                "params": {"name": "move_timeline_clip", "arguments": {"timeline_file": "x", "clip_id": "clip_001"}},
            }
        )
    assert excinfo.value.code == -32602
    assert "missing required property 'timeline_in'" in excinfo.value.message


def test_create_timeline_track_invalid_enum_fails_schema() -> None:
    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "real-tool",
                "method": "tools/call",
                "params": {"name": "create_timeline_track", "arguments": {"timeline_file": "x", "track_type": "subtitle"}},
            }
        )
    assert excinfo.value.code == -32602
    assert "'track_type' must be one of" in excinfo.value.message


def test_apply_timeline_edits_empty_edits_fails_schema() -> None:
    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "real-tool",
                "method": "tools/call",
                "params": {"name": "apply_timeline_edits", "arguments": {"timeline_file": "x", "edits": []}},
            }
        )
    assert excinfo.value.code == -32602
    assert "must have at least 1" in excinfo.value.message


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_schema_rejects_non_finite_number(monkeypatch, bad_value) -> None:
    monkeypatch.setitem(server.TOOLS, "number_tool", _number_tool_entry())

    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "number-tool",
                "method": "tools/call",
                "params": {"name": "number_tool", "arguments": {"value": bad_value}},
            }
        )
    assert excinfo.value.code == -32602
    assert "'value' must be of type" in excinfo.value.message


def test_move_timeline_clip_rejects_non_finite_timeline_in() -> None:
    with pytest.raises(McpError) as excinfo:
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": "real-tool",
                "method": "tools/call",
                "params": {
                    "name": "move_timeline_clip",
                    "arguments": {"timeline_file": "x", "clip_id": "clip_001", "timeline_in": float("nan")},
                },
            }
        )
    assert excinfo.value.code == -32602
    assert "timeline_in" in excinfo.value.message
    assert "PERMISSION_DENIED" not in excinfo.value.message
