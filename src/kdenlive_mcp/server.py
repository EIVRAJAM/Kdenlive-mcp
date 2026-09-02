from __future__ import annotations

import inspect
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kdenlive_mcp import __version__
from kdenlive_mcp.logging import append_tool_log
from kdenlive_mcp.tools.analysis_tools import TOOLS as ANALYSIS_TOOLS
from kdenlive_mcp.tools.audio_tools import TOOLS as AUDIO_TOOLS
from kdenlive_mcp.tools.environment_tools import TOOLS as ENVIRONMENT_TOOLS
from kdenlive_mcp.tools.manifest_tools import TOOLS as MANIFEST_TOOLS
from kdenlive_mcp.tools.media_tools import TOOLS as MEDIA_TOOLS
from kdenlive_mcp.tools.project_tools import TOOLS as PROJECT_TOOLS
from kdenlive_mcp.tools.rough_cut_tools import TOOLS as ROUGH_CUT_TOOLS
from kdenlive_mcp.tools.timeline_tools import TOOLS as TIMELINE_TOOLS
from kdenlive_mcp.tools.workflow_tools import TOOLS as WORKFLOW_TOOLS

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
TOOLS = {
    **ENVIRONMENT_TOOLS,
    **MEDIA_TOOLS,
    **AUDIO_TOOLS,
    **ANALYSIS_TOOLS,
    **ROUGH_CUT_TOOLS,
    **TIMELINE_TOOLS,
    **WORKFLOW_TOOLS,
    **MANIFEST_TOOLS,
    **PROJECT_TOOLS,
}


class McpError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _read_headers(stream: BinaryIO) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            return headers
        decoded = line.decode("ascii").strip()
        if ":" not in decoded:
            raise McpError(-32700, f"Invalid MCP header: {decoded}")
        key, value = decoded.split(":", 1)
        headers[key.lower()] = value.strip()


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    headers = _read_headers(stream)
    if headers is None:
        return None
    length_value = headers.get("content-length")
    if length_value is None:
        raise McpError(-32700, "Missing Content-Length header")
    try:
        length = int(length_value)
    except ValueError as exc:
        raise McpError(-32700, "Invalid Content-Length header") from exc
    body = stream.read(length)
    if len(body) != length:
        raise McpError(-32700, "Unexpected end of stream")
    try:
        message = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise McpError(-32700, "Invalid JSON payload") from exc
    if not isinstance(message, dict):
        raise McpError(-32600, "JSON-RPC message must be an object")
    return message


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def _response(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": message_id, "result": result}


def _error_response(message_id: Any, error: McpError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        payload["data"] = error.data
    return {"jsonrpc": JSONRPC_VERSION, "id": message_id, "error": payload}


_JSON_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "string": lambda value: isinstance(value, str),
    "number": lambda value: (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not math.isnan(value)
        and not math.isinf(value)
    ),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "array": lambda value: isinstance(value, list),
    "object": lambda value: isinstance(value, dict),
    "null": lambda value: value is None,
}


def _matches_json_type(value: Any, json_type: str) -> bool:
    check = _JSON_TYPE_CHECKS.get(json_type)
    if check is None:
        return True
    return check(value)


def _schema_errors(schema: Any, value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed_types = schema_type if isinstance(schema_type, list) else [schema_type]
        if not any(_matches_json_type(value, json_type) for json_type in allowed_types):
            errors.append(f"'{path}' must be of type {allowed_types}")

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for required in schema.get("required") or []:
            if required not in value:
                errors.append(f"missing required property '{required}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"unexpected property '{key}'")
        for key, prop_schema in properties.items():
            if key in value:
                child_path = f"{path}.{key}" if path else key
                errors.extend(_schema_errors(prop_schema, value[key], child_path))
    elif isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"'{path}' must have at least {min_items} item(s)")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                errors.extend(_schema_errors(items, item, f"{path}[{index}]"))

    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"'{path}' must be one of {enum}")

    return errors


def _validate_tool_arguments_schema(tool_name: str, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    errors = _schema_errors(schema, arguments, "")
    if errors:
        raise McpError(-32602, f"Invalid arguments for {tool_name}: {'; '.join(errors)}")


def _invalid_tool_response(tool_name: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": "INVALID_TOOL_RESPONSE",
        "message": "Tool returned an invalid response.",
        "operation": tool_name,
        "warnings": [],
    }


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": definition["description"],
            "inputSchema": definition["inputSchema"],
        }
        for name, definition in TOOLS.items()
    ]


def _call_tool(params: dict[str, Any], request_id: Any = None) -> dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str):
        raise McpError(-32602, "Tool name is required")
    if name not in TOOLS:
        raise McpError(-32602, f"Unknown tool: {name}")

    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise McpError(-32602, "Tool arguments must be an object")

    _validate_tool_arguments_schema(name, TOOLS[name]["inputSchema"], arguments)

    handler = TOOLS[name]["handler"]
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        try:
            signature.bind(**arguments)
        except TypeError as exc:
            raise McpError(-32602, f"Invalid arguments for {name}: {exc}") from exc

    start = time.perf_counter()
    error_type: str | None = None
    error_message: str | None = None
    try:
        result = handler(**arguments)
    except Exception as exc:  # defensive server boundary for unexpected tool failures
        error_type = type(exc).__name__
        error_message = str(exc)
        result = {
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "Tool execution failed unexpectedly.",
            "operation": name,
            "warnings": [],
        }
    if isinstance(result, dict) and result.get("operation") is None:
        result["operation"] = name
    if not isinstance(result, dict) or not isinstance(result.get("success"), bool):
        error_type = "InvalidToolResponse"
        error_message = "Tool returned an invalid response."
        result = _invalid_tool_response(name)
    elif result["success"] is False and (
        not isinstance(result.get("error"), str)
        or result["error"] == ""
        or not isinstance(result.get("message"), str)
        or result["message"] == ""
    ):
        error_type = "InvalidToolResponse"
        error_message = "Tool returned an invalid response."
        result = _invalid_tool_response(name)
    elif result.get("operation") is not None and (
        not isinstance(result["operation"], str) or result["operation"] == ""
    ):
        error_type = "InvalidToolResponse"
        error_message = "Tool returned an invalid response."
        result = _invalid_tool_response(name)
    if isinstance(result, dict):
        warnings = result.get("warnings")
        if warnings is None:
            result["warnings"] = []
        elif not isinstance(warnings, list):
            error_type = "InvalidToolResponse"
            error_message = "Tool returned an invalid response."
            result = _invalid_tool_response(name)
    duration_ms = (time.perf_counter() - start) * 1000
    try:
        append_tool_log(
            request_id=request_id,
            tool_name=name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            error_type=error_type,
            message=error_message,
        )
    except Exception:
        pass

    is_error = not bool(result.get("success", False))
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2, ensure_ascii=False),
            }
        ],
        "isError": is_error,
    }


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if not isinstance(method, str):
        raise McpError(-32600, "JSON-RPC method is required")
    if params is not None and not isinstance(params, dict):
        raise McpError(-32602, "JSON-RPC params must be an object")

    if method.startswith("notifications/"):
        return None
    if message_id is None:
        return None

    if method == "initialize":
        return _response(
            message_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kdenlive-mcp", "version": __version__},
            },
        )
    if method == "ping":
        return _response(message_id, {})
    if method == "tools/list":
        return _response(message_id, {"tools": _tool_definitions()})
    if method == "tools/call":
        return _response(message_id, _call_tool(params, request_id=message_id))
    if method == "resources/list":
        return _response(message_id, {"resources": []})
    if method == "prompts/list":
        return _response(message_id, {"prompts": []})

    raise McpError(-32601, f"Method not found: {method}")


def serve(input_stream: BinaryIO | None = None, output_stream: BinaryIO | None = None) -> None:
    input_stream = input_stream or sys.stdin.buffer
    output_stream = output_stream or sys.stdout.buffer

    while True:
        try:
            message = read_message(input_stream)
            if message is None:
                return
            try:
                response = handle_request(message)
            except McpError as exc:
                response = _error_response(message.get("id"), exc)
            if response is not None:
                write_message(output_stream, response)
        except McpError as exc:
            write_message(output_stream, _error_response(None, exc))


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
