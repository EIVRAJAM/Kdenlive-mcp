from __future__ import annotations

import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_gate.sh"


def test_release_gate_script_exists() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.read_text(encoding="utf-8")


def test_release_gate_script_has_bash_shebang_and_is_runnable() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("#!/usr/bin/env bash")
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "release_gate.sh should be executable; run via bash otherwise"


def test_release_gate_contains_expected_gates() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "scripts/dev_check.sh" in text
    assert "KDENLIVE_MCP_RUN_STDIO_SMOKE" in text
    assert "KDENLIVE_MCP_RUN_RELIABILITY" in text
    assert "KDENLIVE_MCP_RUN_MLT_CHECK" in text
    assert "KDENLIVE_MCP_MLT_PROJECT" in text


def test_release_gate_uses_safe_shell_defaults() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in text
    assert "shell=" not in text
    assert "rm " not in text
    assert "rm -rf" not in text


def test_release_gate_reports_mlt_skip_and_manual_steps() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "SKIPPED" in text
    assert "Manual steps still required" in text
    assert "Manual Kdenlive open verification" in text