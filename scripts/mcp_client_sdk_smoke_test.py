from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = REPO_ROOT / "src" / "kdenlive_mcp" / "server.py"

EXPECTED_TOOL_COUNT = 60
REQUIRED_TOOLS = [
    "health_check",
    "get_environment",
    "scan_media",
    "create_vlog_rough_cut_project",
    "apply_timeline_to_working_project",
]


def _blocked_result() -> dict[str, object]:
    return {
        "success": False,
        "blocked": "mcp-sdk-unavailable",
        "sdk": "mcp",
        "message": "The official Python MCP SDK is not installed locally.",
        "install": "python3 -m pip install 'mcp>=1.0'",
        "rerun": f"{sys.executable} {Path(__file__).resolve()}",
    }


async def _run_smoke() -> dict[str, object]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        env={**os.environ, "KDENLIVE_MCP_LOG_FILE": "off"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server_name = init.serverInfo.name
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            missing = [name for name in REQUIRED_TOOLS if name not in tool_names]
            return {
                "success": server_name == "kdenlive-mcp"
                and len(tool_names) == EXPECTED_TOOL_COUNT
                and not missing,
                "sdk": "mcp",
                "server": server_name,
                "tool_count": len(tool_names),
                "expected_tool_count": EXPECTED_TOOL_COUNT,
                "required_tools_present": not missing,
                "missing_tools": missing,
            }


def main() -> int:
    if importlib.util.find_spec("mcp") is None:
        result = _blocked_result()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2
    try:
        result = asyncio.run(_run_smoke())
    except Exception as exc:  # real smoke failure, not a blocked SDK
        result = {"success": False, "sdk": "mcp", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
