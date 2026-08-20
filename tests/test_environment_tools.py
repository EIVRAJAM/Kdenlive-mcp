from __future__ import annotations

from pathlib import Path

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


def test_kdenlive_version_falls_back_to_flatpak_info(monkeypatch) -> None:
    def fake_run(command):
        if command[:3] == ["flatpak", "run", "--command=kdenlive"]:
            return environment_tools.CommandResult(
                command=command,
                available=True,
                returncode=1,
                stdout="",
                stderr="error: Unable to allocate instance id",
                error="Command failed",
            )
        if command == ["flatpak", "info", "org.kde.kdenlive"]:
            return environment_tools.CommandResult(
                command=command,
                available=True,
                returncode=0,
                stdout="Version: 26.04.3\nRuntime: org.kde.Platform/x86_64/6.10\n",
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(environment_tools, "run_command", fake_run)

    result = environment_tools.get_kdenlive_version()

    assert result["success"] is True
    assert result["version"] == "26.04.3"
    assert result["source"] == "flatpak_info"
    assert result["execution_error"] == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"


def test_mlt_version_falls_back_to_flatpak_installation_scan(monkeypatch, tmp_path: Path) -> None:
    lib_dir = tmp_path / "files" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "libmlt-7.so.7.40.0").touch()

    def fake_run(command):
        if command == ["melt", "-version"]:
            return environment_tools.CommandResult(
                command=command,
                available=False,
                returncode=None,
                stdout="",
                stderr="",
                error="Executable not found",
            )
        if command[:3] == ["flatpak", "run", "--command=melt"]:
            return environment_tools.CommandResult(
                command=command,
                available=True,
                returncode=1,
                stdout="",
                stderr="error: Unable to allocate instance id",
                error="Command failed",
            )
        if command == ["flatpak", "info", "--show-location", "org.kde.kdenlive"]:
            return environment_tools.CommandResult(
                command=command,
                available=True,
                returncode=0,
                stdout=str(tmp_path),
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr(environment_tools, "run_command", fake_run)

    result = environment_tools.get_mlt_version()

    assert result["success"] is True
    assert result["mlt_version"] == "7.40.0"
    assert result["source"] == "flatpak_installation_scan"
    assert result["execution_error"] == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
