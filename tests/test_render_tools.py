from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.adapters.commands import CommandResult
from kdenlive_mcp.tools import render_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"


def _success_result(command: list[str], timeout: float | None = None) -> CommandResult:
    return CommandResult(
        command=command,
        available=True,
        returncode=0,
        stdout="",
        stderr="",
    )


def _rendering_result(command: list[str]) -> CommandResult:
    consumer = next(part for part in command if part.startswith("avformat:"))
    output_path = Path(consumer.split(":", 1)[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"rendered")
    return _success_result(command)


def _failure_result(command: list[str], timeout: float | None = None) -> CommandResult:
    return CommandResult(
        command=command,
        available=True,
        returncode=1,
        stdout="",
        stderr="melt: consumer failed",
    )


def _sandbox_result(command: list[str], timeout: float | None = None) -> CommandResult:
    return CommandResult(
        command=command,
        available=True,
        returncode=1,
        stdout="",
        stderr="error: Unable to allocate instance id",
    )


def _valid_probe() -> dict[str, object]:
    return {"duration": 4.56, "width": 720, "height": 1280}


def _allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))


def _mock_valid_probe(monkeypatch) -> None:
    monkeypatch.setattr(render_tools, "_probe_preview", lambda path: _valid_probe())


def test_render_preview_builds_flatpak_melt_command(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    _mock_valid_probe(monkeypatch)
    output = tmp_path / "preview.mp4"

    captured: list[list[str]] = []
    monkeypatch.setattr(
        render_tools,
        "run_command",
        lambda command, timeout=150.0: captured.append(command) or _rendering_result(command),
    )

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
        width=720,
        height=1280,
    )

    assert result["success"] is True
    assert result["operation"] == "render_preview"
    assert result["output"] == str(output)
    assert len(captured) == 1
    command = captured[0]
    assert command[0] == "timeout"
    assert command[2] == "flatpak"
    assert command[3] == "run"
    assert "--command=melt" in command
    assert "org.kde.kdenlive" in command
    assert command[-6] == f"avformat:{output}"
    assert "width=720" in command
    assert "height=1280" in command


def test_render_preview_rejects_existing_output_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output = tmp_path / "manual_two_clips_timeline_preview.mp4"
    output.write_bytes(b"existing")
    calls: list[object] = []
    monkeypatch.setattr(render_tools, "run_command", lambda command, timeout=300.0: calls.append(command) or _failure_result(command))

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
    )

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert calls == []
    assert output.read_bytes() == b"existing"


def test_render_preview_respects_overwrite(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    _mock_valid_probe(monkeypatch)
    output = tmp_path / "preview.mp4"
    output.write_bytes(b"old")
    captured: list[list[str]] = []
    monkeypatch.setattr(
        render_tools,
        "run_command",
        lambda command, timeout=150.0: captured.append(command) or _rendering_result(command),
    )

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
        overwrite=True,
    )

    assert result["success"] is True
    assert output.read_bytes() == b"rendered"
    assert len(captured) == 1


def test_render_preview_rejects_paths_outside_allowlist(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    outside = tmp_path.parent / "outside.mp4"

    result = render_tools.render_preview(
        project=str(outside),
        output_directory=str(tmp_path),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_render_preview_fails_when_zero_returncode_but_no_output(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setattr(render_tools, "run_command", _success_result)

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "MLT_ERROR"
    assert not (tmp_path / "preview.mp4").exists()


def test_render_preview_reports_mlt_error_on_real_failure(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setattr(render_tools, "run_command", _failure_result)

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "MLT_ERROR"
    assert result["operation"] == "render_preview"
    assert result["render"]["returncode"] == 1


def test_render_preview_reports_sandbox_unavailable_structured(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setattr(render_tools, "run_command", _sandbox_result)

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
    assert isinstance(result["message"], str) and result["message"]
    assert result["warnings"] == [
        {
            "code": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
            "message": "Render preview could not run Flatpak melt in this environment.",
        }
    ]
    assert not (tmp_path / "preview.mp4").exists()


def _rendered_and_probe(monkeypatch, tmp_path: Path, probe) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setattr(
        render_tools,
        "run_command",
        lambda command, timeout=150.0: _rendering_result(command),
    )
    monkeypatch.setattr(render_tools, "_probe_preview", lambda path: probe)


def test_render_preview_rejects_truncated_output(monkeypatch, tmp_path: Path) -> None:
    _rendered_and_probe(monkeypatch, tmp_path, None)

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_RENDER_OUTPUT"
    assert result["render"]["size_bytes"] > 0
    assert result["probe"] is None
    assert (tmp_path / "preview.mp4").exists()


def test_render_preview_rejects_zero_duration_output(monkeypatch, tmp_path: Path) -> None:
    _rendered_and_probe(monkeypatch, tmp_path, {"duration": 0.0, "width": 720, "height": 1280})

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_RENDER_OUTPUT"


def test_render_preview_rejects_dimension_mismatch(monkeypatch, tmp_path: Path) -> None:
    _rendered_and_probe(monkeypatch, tmp_path, {"duration": 4.0, "width": 640, "height": 1280})

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_RENDER_OUTPUT"


def test_render_preview_success_includes_probe(monkeypatch, tmp_path: Path) -> None:
    _rendered_and_probe(monkeypatch, tmp_path, _valid_probe())

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
    )

    assert result["success"] is True
    assert result["render"]["probe"]["duration"] == 4.56
    assert result["render"]["probe"]["width"] == 720
    assert result["render"]["probe"]["height"] == 1280


def test_render_preview_overwrite_does_not_report_old_output_success(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output = tmp_path / "preview.mp4"
    output.write_bytes(b"old-valid-content")
    monkeypatch.setattr(render_tools, "run_command", _failure_result)
    monkeypatch.setattr(render_tools, "_probe_preview", lambda path: _valid_probe())

    result = render_tools.render_preview(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        name="preview",
        overwrite=True,
    )

    assert result["success"] is False
    assert not output.exists()
