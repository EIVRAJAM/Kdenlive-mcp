from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.services.vlog_workflow_service import create_vlog_rough_cut_project


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
TEMPLATE = RECON_DIR / "manual_empty_vertical.kdenlive"


def _allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")


def test_create_vlog_rough_cut_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

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
    assert result["steps"]["kdenlive_project"]["timeline_clip_count"] == 4
    assert result["steps"]["kdenlive_project"]["missing_media_count"] == 0


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
