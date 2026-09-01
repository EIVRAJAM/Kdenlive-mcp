from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TOOLS = [
    "health_check",
    "get_environment",
    "scan_media",
    "create_vlog_rough_cut_project",
    "export_timeline_to_kdenlive_template",
]


def _frame(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _read_message(stream) -> dict[str, object] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("ascii").strip().split(":", 1)
        headers[key.lower()] = value.strip()
    length = int(headers["content-length"])
    body = stream.read(length)
    if len(body) != length:
        raise RuntimeError("truncated MCP response body")
    return json.loads(body.decode("utf-8"))


def main() -> int:
    command = [sys.executable, str(REPO_ROOT / "src" / "kdenlive_mcp" / "server.py")]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=str(REPO_ROOT),
        shell=False,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    result: dict[str, object] = {
        "success": False,
        "server": None,
        "tool_count": None,
        "required_tools_present": None,
        "error": None,
    }
    try:
        process.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        process.stdin.flush()
        init_response = _read_message(process.stdout)
        if init_response is None:
            raise RuntimeError("no initialize response")
        init_result = init_response.get("result") or {}
        server_info = init_result.get("serverInfo") or {}
        capabilities = init_result.get("capabilities") or {}
        if server_info.get("name") != "kdenlive-mcp":
            raise RuntimeError(f"unexpected serverInfo: {server_info}")
        if not isinstance(capabilities.get("tools"), dict):
            raise RuntimeError("capabilities.tools missing")

        process.stdin.write(
            _frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        )
        process.stdin.flush()
        list_response = _read_message(process.stdout)
        if list_response is None:
            raise RuntimeError("no tools/list response")
        tools = (list_response.get("result") or {}).get("tools") or []
        tool_names = {tool.get("name") for tool in tools}
        missing = [name for name in REQUIRED_TOOLS if name not in tool_names]
        if missing:
            raise RuntimeError(f"missing tools: {missing}")

        result = {
            "success": True,
            "server": server_info.get("name"),
            "tool_count": len(tool_names),
            "required_tools_present": True,
            "error": None,
        }
    except Exception as exc:  # keep output structured even on failure
        result["error"] = str(exc)
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
