from __future__ import annotations

import io
import json

from kdenlive_mcp.server import handle_request, read_message, write_message


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
