from pathlib import Path

from kdenlive_mcp.services.lock_service import get_project_lock, lock_project, unlock_project


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"


def _allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))


def test_lock_project_creates_lock_file(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    result = lock_project(
        project=str(SOURCE_PROJECT),
        owner="codex-test",
        lock_directory=str(tmp_path / ".locks"),
    )

    assert result["success"] is True
    assert result["locked"] is True
    assert result["already_locked"] is False
    assert Path(result["lock_file"]).exists()
    assert result["lock"]["owner"] == "codex-test"
    assert result["lock"]["project"] == str(SOURCE_PROJECT.resolve())


def test_lock_project_is_idempotent_for_same_owner(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    kwargs = {
        "project": str(SOURCE_PROJECT),
        "owner": "codex-test",
        "lock_directory": str(tmp_path / ".locks"),
    }

    first = lock_project(**kwargs)
    second = lock_project(**kwargs)

    assert first["success"] is True
    assert second["success"] is True
    assert second["already_locked"] is True
    assert second["lock_file"] == first["lock_file"]


def test_lock_project_rejects_different_owner(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    lock_project(
        project=str(SOURCE_PROJECT),
        owner="owner-a",
        lock_directory=str(tmp_path / ".locks"),
    )

    result = lock_project(
        project=str(SOURCE_PROJECT),
        owner="owner-b",
        lock_directory=str(tmp_path / ".locks"),
    )

    assert result["success"] is False
    assert result["error"] == "PROJECT_LOCKED"
    assert result["lock"]["owner"] == "owner-a"


def test_unlock_project_requires_owner_unless_forced(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    locked = lock_project(
        project=str(SOURCE_PROJECT),
        owner="owner-a",
        lock_directory=str(tmp_path / ".locks"),
    )

    denied = unlock_project(
        project=str(SOURCE_PROJECT),
        owner="owner-b",
        lock_directory=str(tmp_path / ".locks"),
    )
    forced = unlock_project(
        project=str(SOURCE_PROJECT),
        owner="owner-b",
        lock_directory=str(tmp_path / ".locks"),
        force=True,
    )

    assert denied["success"] is False
    assert denied["error"] == "PROJECT_LOCKED"
    assert forced["success"] is True
    assert forced["unlocked"] is True
    assert not Path(locked["lock_file"]).exists()


def test_get_project_lock_reports_status(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    unlocked = get_project_lock(
        project=str(SOURCE_PROJECT),
        lock_directory=str(tmp_path / ".locks"),
    )
    lock_project(
        project=str(SOURCE_PROJECT),
        owner="codex-test",
        lock_directory=str(tmp_path / ".locks"),
    )
    locked = get_project_lock(
        project=str(SOURCE_PROJECT),
        lock_directory=str(tmp_path / ".locks"),
    )

    assert unlocked["success"] is True
    assert unlocked["locked"] is False
    assert locked["success"] is True
    assert locked["locked"] is True
    assert locked["lock"]["owner"] == "codex-test"


def test_lock_project_requires_output_allowlist(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path / "allowed"))

    result = lock_project(
        project=str(SOURCE_PROJECT),
        lock_directory=str(tmp_path / "denied"),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
