from __future__ import annotations

import io
import json

from kdenlive_mcp.server import handle_request, read_message, write_message
from kdenlive_mcp.logging import append_tool_log


def _framed(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


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
