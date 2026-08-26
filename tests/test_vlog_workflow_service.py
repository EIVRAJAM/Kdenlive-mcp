from __future__ import annotations

import hashlib
from pathlib import Path

from kdenlive_mcp.adapters.commands import CommandResult
from kdenlive_mcp.services import vlog_workflow_service
from kdenlive_mcp.services.vlog_workflow_service import create_vlog_rough_cut_project


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
TEMPLATE = RECON_DIR / "manual_empty_vertical.kdenlive"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")


def test_create_vlog_rough_cut_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    media_files = [RECON_DIR / "sample1.mp4", RECON_DIR / "sample_vertical.mp4"]
    before_hashes = {path: _sha256(path) for path in media_files}

    result = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="vlog_ai_001",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    assert result["success"] is True
    assert result["operation"] == "create_vlog_rough_cut_project"
    assert Path(result["project"]).name == "vlog_ai_001.kdenlive"
    assert Path(result["artifacts"]["rough_cut_plan"]).exists()
    assert Path(result["artifacts"]["timeline"]).exists()
    assert Path(result["artifacts"]["kdenlive_project"]).exists()
    assert result["steps"]["rough_cut_plan"]["planned_duration"] == 4.0
    assert result["steps"]["timeline"]["clip_count"] == 4
    assert result["steps"]["timeline"]["marker_count"] == 2
    assert result["steps"]["kdenlive_project"]["timeline_clip_count"] == 4
    assert result["steps"]["kdenlive_project"]["marker_count"] == 2
    assert result["steps"]["kdenlive_project"]["guide_count"] == 2
    assert result["steps"]["kdenlive_project"]["missing_media_count"] == 0
    assert result["steps"]["mlt_load"] == {"checked": False, "valid": None}
    assert result["partial_outputs"] == result["artifacts"]
    assert result["warnings"] == []
    assert {path: _sha256(path) for path in media_files} == before_hashes


def test_create_vlog_rough_cut_project_reports_failed_step(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    first = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="existing",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )
    second = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="existing",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    assert first["success"] is True
    assert second["success"] is False
    assert second["failed_step"] == "create_rough_cut_plan_file"
    assert second["error"] == "OUTPUT_EXISTS"
    assert second["partial_outputs"] == {}


def test_create_vlog_rough_cut_project_reports_partial_outputs_after_late_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _allow(monkeypatch, tmp_path)
    existing_project = tmp_path / "late_failure.kdenlive"
    existing_project.write_text("already here", encoding="utf-8")

    result = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="late_failure",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    assert result["success"] is False
    assert result["failed_step"] == "export_timeline_to_kdenlive_template"
    assert result["error"] == "OUTPUT_EXISTS"
    assert set(result["partial_outputs"]) == {"rough_cut_plan", "timeline"}
    assert Path(result["partial_outputs"]["rough_cut_plan"]).exists()
    assert Path(result["partial_outputs"]["timeline"]).exists()


def test_create_vlog_rough_cut_project_can_validate_mlt_load(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    def fake_run(command, timeout):
        return CommandResult(
            command=command,
            available=True,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(vlog_workflow_service, "run_command", fake_run)

    result = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="mlt_checked",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
        check_mlt=True,
    )

    assert result["success"] is True
    assert result["steps"]["mlt_load"]["checked"] is True
    assert result["steps"]["mlt_load"]["valid"] is True
    assert result["steps"]["mlt_load"]["status"] == "loaded"


def test_create_vlog_rough_cut_project_fails_when_mlt_load_fails(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    def fake_run(command, timeout):
        return CommandResult(
            command=command,
            available=True,
            returncode=1,
            stdout="",
            stderr="invalid",
            error="Command failed",
        )

    monkeypatch.setattr(vlog_workflow_service, "run_command", fake_run)

    result = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="mlt_failed",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
        check_mlt=True,
    )

    assert result["success"] is False
    assert result["failed_step"] == "validate_mlt_load"
    assert result["error"] == "MLT_ERROR"
    assert set(result["partial_outputs"]) == {"rough_cut_plan", "timeline", "kdenlive_project"}


def test_create_vlog_rough_cut_project_preflight_blocks_partial_writes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))

    result = create_vlog_rough_cut_project(
        folder=str(RECON_DIR),
        template_project=str(TEMPLATE),
        output_directory=str(tmp_path),
        name="denied_project_dir",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    assert result["success"] is False
    assert result["failed_step"] == "preflight"
    assert result["error"] == "PERMISSION_DENIED"
    assert list(tmp_path.iterdir()) == []
