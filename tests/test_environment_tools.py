from __future__ import annotations

from kdenlive_mcp.tools import environment_tools


def test_health_check() -> None:
    result = environment_tools.health_check()

    assert result["success"] is True
    assert result["service"] == "kdenlive-mcp"
    assert "environment_detection" in result["capabilities"]


def test_get_environment_contains_expected_sections() -> None:
    result = environment_tools.get_environment()

    assert result["success"] is True
    assert "python" in result
    assert "platform" in result
    assert "binaries" in result
    assert "settings" in result


def test_version_payload_when_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr(environment_tools, "run_command", lambda command: environment_tools.CommandResult(
        command=command,
        available=False,
        returncode=None,
        stdout="",
        stderr="",
        error="Executable not found",
    ))

    result = environment_tools.get_ffmpeg_version()

    assert result["success"] is False
    assert result["tool"] == "ffmpeg"
    assert result["error"] == "Executable not found"
