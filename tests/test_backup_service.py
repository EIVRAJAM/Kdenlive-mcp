from pathlib import Path

from kdenlive_mcp.services.backup_service import backup_project, clone_project, list_project_versions


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"


def test_backup_project_creates_timestamped_copy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    result = backup_project(
        project=str(SOURCE_PROJECT),
        backup_directory=str(tmp_path / ".backups"),
        label="unit",
    )

    assert result["success"] is True
    backup = Path(result["backup"])
    assert backup.exists()
    assert backup.parent == tmp_path / ".backups"
    assert backup.name.startswith("manual_two_clips_timeline_unit_")
    assert backup.read_bytes() == SOURCE_PROJECT.read_bytes()


def test_clone_project_creates_next_ai_copy_and_backup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    first = clone_project(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
    )
    second = clone_project(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
    )

    assert first["success"] is True
    assert second["success"] is True
    assert Path(first["clone"]).name == "manual_two_clips_timeline_ai_001.kdenlive"
    assert Path(second["clone"]).name == "manual_two_clips_timeline_ai_002.kdenlive"
    assert Path(first["backup"]).exists()
    assert Path(second["backup"]).exists()
    assert Path(first["clone"]).read_bytes() == SOURCE_PROJECT.read_bytes()


def test_clone_project_can_skip_backup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    result = clone_project(
        project=str(SOURCE_PROJECT),
        output_directory=str(tmp_path),
        create_backup=False,
    )

    assert result["success"] is True
    assert result["backup"] is None
    assert Path(result["clone"]).exists()


def test_backup_project_requires_output_allowlist(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path / "allowed"))

    result = backup_project(
        project=str(SOURCE_PROJECT),
        backup_directory=str(tmp_path / "denied"),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_list_project_versions_reports_working_copies_and_backups(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    clone_project(project=str(SOURCE_PROJECT), output_directory=str(tmp_path))
    clone_project(project=str(SOURCE_PROJECT), output_directory=str(tmp_path))

    result = list_project_versions(
        project=str(SOURCE_PROJECT),
        project_directory=str(tmp_path),
        backup_directory=str(tmp_path / ".backups"),
    )

    assert result["success"] is True
    assert result["base_stem"] == "manual_two_clips_timeline"
    assert result["working_copy_count"] == 2
    assert result["backup_count"] == 2
    assert [item["filename"] for item in result["working_copies"]] == [
        "manual_two_clips_timeline_ai_001.kdenlive",
        "manual_two_clips_timeline_ai_002.kdenlive",
    ]
    assert all(item["label"] == "ai" for item in result["working_copies"])
    assert result["original"] is None


def test_list_project_versions_requires_project_directory_allowlist(monkeypatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))

    result = list_project_versions(
        project=str(SOURCE_PROJECT),
        project_directory=str(project_dir),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
