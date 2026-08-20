from pathlib import Path

from kdenlive_mcp.services.project_workflow_service import prepare_working_project


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"


def test_prepare_working_project_clones_backs_up_and_locks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    result = prepare_working_project(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        owner="codex-test",
    )

    assert result["success"] is True
    assert result["operation"] == "prepare_working_project"
    assert Path(result["working_project"]).name == "manual_two_clips_timeline_ai_001.kdenlive"
    assert Path(result["working_project"]).exists()
    assert Path(result["backup"]).exists()
    assert Path(result["lock_file"]).exists()
    assert result["lock"]["lock"]["owner"] == "codex-test"


def test_prepare_working_project_requires_output_to_be_project_allowed(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(output_dir))

    result = prepare_working_project(
        project=str(SOURCE_PROJECT),
        output_directory=str(output_dir),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
