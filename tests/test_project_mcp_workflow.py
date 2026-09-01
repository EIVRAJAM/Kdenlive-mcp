from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from kdenlive_mcp.server import handle_request


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SOURCE_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"


def _call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": name,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    return json.loads(response["result"]["content"][0]["text"])


def _allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lock_blocks_prepare_working_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    project = str(SOURCE_PROJECT)
    lock_dir = str(tmp_path / "locks")

    locked = _call("lock_project", {"project": project, "owner": "alice", "lock_directory": lock_dir})
    assert locked["success"] is True
    assert locked["locked"] is True

    prepared = _call(
        "prepare_working_project",
        {"project": project, "output_directory": str(tmp_path), "owner": "bob", "lock_directory": lock_dir},
    )
    assert prepared["success"] is False
    assert prepared["error"] == "PROJECT_LOCKED"
    assert prepared["operation"] == "prepare_working_project"
    assert isinstance(prepared["message"], str) and prepared["message"]
    assert not (tmp_path / "manual_two_clips_timeline_ai_001.kdenlive").exists()

    unlocked = _call("unlock_project", {"project": project, "owner": "alice", "lock_directory": lock_dir})
    assert unlocked["success"] is True
    assert unlocked["unlocked"] is True

    prepared_after = _call(
        "prepare_working_project",
        {"project": project, "output_directory": str(tmp_path), "owner": "bob", "lock_directory": lock_dir},
    )
    assert prepared_after["success"] is True
    assert (tmp_path / "manual_two_clips_timeline_ai_001.kdenlive").exists()


def test_clone_restore_and_list_versions(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    project = str(SOURCE_PROJECT)
    original_hash = _sha256(SOURCE_PROJECT)

    first = _call("clone_project", {"project": project, "output_directory": str(tmp_path)})
    assert first["success"] is True
    ai_001 = Path(first["clone"])
    assert ai_001.name == "manual_two_clips_timeline_ai_001.kdenlive"
    assert ai_001.exists()

    second = _call("clone_project", {"project": project, "output_directory": str(tmp_path)})
    assert second["success"] is True
    ai_002 = Path(second["clone"])
    assert ai_002.name == "manual_two_clips_timeline_ai_002.kdenlive"
    assert ai_002.exists()

    listed = _call("list_project_versions", {"project": project, "project_directory": str(tmp_path)})
    assert listed["success"] is True
    working_names = {item["filename"] for item in listed["working_copies"]}
    assert "manual_two_clips_timeline_ai_001.kdenlive" in working_names
    assert "manual_two_clips_timeline_ai_002.kdenlive" in working_names

    restored = _call(
        "restore_project_version",
        {"project": project, "version": str(ai_001), "output_directory": str(tmp_path)},
    )
    assert restored["success"] is True
    restored_path = Path(restored["restored_project"])
    assert restored_path.name == "manual_two_clips_timeline_restored_001.kdenlive"
    assert restored_path.exists()
    ET.parse(restored_path)

    assert _sha256(SOURCE_PROJECT) == original_hash


def test_restore_rejects_missing_version(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    project = str(SOURCE_PROJECT)

    result = _call(
        "restore_project_version",
        {
            "project": project,
            "version": str(tmp_path / "does_not_exist.kdenlive"),
            "output_directory": str(tmp_path),
        },
    )

    assert result["success"] is False
    assert result["error"] == "PROJECT_NOT_FOUND"
    assert isinstance(result["message"], str) and result["message"]
    assert result["operation"] == "restore_project_version"
    assert not list(tmp_path.glob("*restored_*.kdenlive"))


def test_prepare_stops_before_clone_on_invalid_lock_directory(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    project = str(SOURCE_PROJECT)
    bad_lock_dir = str(tmp_path.parent / "outside_locks")

    result = _call(
        "prepare_working_project",
        {"project": project, "output_directory": str(tmp_path), "owner": "alice", "lock_directory": bad_lock_dir},
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
    assert isinstance(result["message"], str) and result["message"]
    assert result["operation"] == "prepare_working_project"
    assert not list(tmp_path.glob("*_ai_*.kdenlive"))
    assert not list(tmp_path.glob("*.kdenlive"))