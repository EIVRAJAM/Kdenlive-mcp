from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "mcp_stdio_smoke_test.py"


def test_mcp_stdio_smoke_script_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        shell=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["success"] is True
    assert output["server"] == "kdenlive-mcp"
    assert output["required_tools_present"] is True
    assert output["tool_count"] >= 5
