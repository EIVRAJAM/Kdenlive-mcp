from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kdenlive_mcp.server import handle_request
from kdenlive_mcp.tools import project_tools


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


def _assert_ok(payload: dict[str, object], operation: str) -> dict[str, object]:
    assert isinstance(payload["success"], bool)
    assert payload.get("operation") == operation
    if "warnings" in payload:
        assert isinstance(payload["warnings"], list)
    if "partial_outputs" in payload:
        assert isinstance(payload["partial_outputs"], dict)
    return payload


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


def test_working_copy_edit_flow_restore(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    project = str(SOURCE_PROJECT)
    original_hash = _sha256(SOURCE_PROJECT)

    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": project,
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    working_copy = Path(prepared["working_project"])
    assert working_copy.name == "manual_two_clips_timeline_ai_001.kdenlive"
    assert working_copy.exists()
    assert Path(prepared["lock_file"]).exists()
    ET.parse(working_copy)

    plan = _assert_ok(
        _call(
            "create_rough_cut_plan_file",
            {
                "folder": str(RECON_DIR),
                "output_directory": str(tmp_path),
                "name": "flow",
                "target_duration": 4,
                "recursive": False,
                "max_files": 1,
                "remove_silence": False,
            },
        ),
        "create_rough_cut_plan_file",
    )
    timeline = _assert_ok(
        _call("create_timeline_from_rough_cut_plan", {"plan_file": plan["plan_file"]}),
        "create_timeline_from_rough_cut_plan",
    )
    saved = _assert_ok(
        _call(
            "save_timeline",
            {"timeline": timeline["timeline"], "output_directory": str(tmp_path), "name": "flow_timeline"},
        ),
        "save_timeline",
    )
    edited = _assert_ok(
        _call(
            "apply_timeline_edits",
            {
                "timeline_file": saved["timeline_file"],
                "edits": [{"operation": "insert_gap", "position": 3.0, "duration": 1.0}],
                "output_directory": str(tmp_path),
                "name": "flow_edited",
                "dry_run": False,
            },
        ),
        "apply_timeline_edits",
    )
    exported = _assert_ok(
        _call(
            "export_timeline_to_kdenlive_template",
            {
                "timeline_file": edited["timeline_file"],
                "template_project": str(working_copy),
                "output_directory": str(tmp_path),
                "name": "edited_from_working",
            },
        ),
        "export_timeline_to_kdenlive_template",
    )
    edited_project = Path(exported["project"])
    assert edited_project.exists()
    ET.parse(edited_project)

    listed = _assert_ok(
        _call("list_project_versions", {"project": project, "project_directory": str(tmp_path)}),
        "list_project_versions",
    )
    working_names = {item["filename"] for item in listed["working_copies"]}
    assert "manual_two_clips_timeline_ai_001.kdenlive" in working_names

    restored = _assert_ok(
        _call(
            "restore_project_version",
            {"project": project, "version": str(working_copy), "output_directory": str(tmp_path)},
        ),
        "restore_project_version",
    )
    restored_path = Path(restored["restored_project"])
    assert restored_path.name == "manual_two_clips_timeline_restored_001.kdenlive"
    assert restored_path.exists()
    ET.parse(restored_path)

    assert _sha256(SOURCE_PROJECT) == original_hash


def test_apply_timeline_to_working_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    project = str(SOURCE_PROJECT)
    original_hash = _sha256(SOURCE_PROJECT)

    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": project,
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    working_copy = Path(prepared["working_project"])
    working_copy_hash = _sha256(working_copy)

    plan = _assert_ok(
        _call(
            "create_rough_cut_plan_file",
            {
                "folder": str(RECON_DIR),
                "output_directory": str(tmp_path),
                "name": "wc_flow",
                "target_duration": 4,
                "recursive": False,
                "max_files": 1,
                "remove_silence": False,
            },
        ),
        "create_rough_cut_plan_file",
    )
    timeline = _assert_ok(
        _call("create_timeline_from_rough_cut_plan", {"plan_file": plan["plan_file"]}),
        "create_timeline_from_rough_cut_plan",
    )
    saved = _assert_ok(
        _call(
            "save_timeline",
            {"timeline": timeline["timeline"], "output_directory": str(tmp_path), "name": "wc_timeline"},
        ),
        "save_timeline",
    )

    result = _assert_ok(
        _call(
            "apply_timeline_to_working_project",
            {
                "working_project": str(working_copy),
                "timeline_file": saved["timeline_file"],
                "output_directory": str(tmp_path),
            },
        ),
        "apply_timeline_to_working_project",
    )

    assert result["output_project"].endswith(".kdenlive")
    output = Path(result["output_project"])
    assert output.exists()
    assert output != working_copy
    assert output.name.startswith(working_copy.stem)
    ET.parse(output)

    inspected = _call("inspect_project", {"project": str(output)})
    assert inspected["success"] is True
    data = inspected["data"]
    active_sequence = next(sequence for sequence in data["sequences"] if sequence["id"] == data["active_sequence_id"])
    assert len(active_sequence["timeline_clips"]) > 0

    assert _sha256(SOURCE_PROJECT) == original_hash
    assert _sha256(working_copy) == working_copy_hash


def test_apply_timeline_to_working_project_rejects_outside_allowlist(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    outside = tmp_path.parent / "outside.kdenlive"

    result = _call(
        "apply_timeline_to_working_project",
        {"working_project": str(outside), "timeline_file": "x"},
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
    assert result["operation"] == "apply_timeline_to_working_project"


def test_apply_timeline_to_working_project_rejects_unsupported_timeline_schema(
    monkeypatch, tmp_path: Path
) -> None:
    _allow(monkeypatch, tmp_path)
    project = str(SOURCE_PROJECT)
    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": project,
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    working_copy = prepared["working_project"]
    bad_timeline = tmp_path / "future.timeline.json"
    bad_timeline.write_text(json.dumps({"kind": "kdenlive_mcp_timeline", "schema_version": 2}), encoding="utf-8")

    result = _call(
        "apply_timeline_to_working_project",
        {
            "working_project": working_copy,
            "timeline_file": str(bad_timeline),
            "output_directory": str(tmp_path),
        },
    )

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_SCHEMA_VERSION"
    assert result["operation"] == "apply_timeline_to_working_project"


def _prepare_working_copy_and_timeline(monkeypatch, tmp_path: Path) -> tuple[str, str]:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    project = str(SOURCE_PROJECT)
    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": project,
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    plan = _assert_ok(
        _call(
            "create_rough_cut_plan_file",
            {
                "folder": str(RECON_DIR),
                "output_directory": str(tmp_path),
                "name": "mlt_flow",
                "target_duration": 4,
                "recursive": False,
                "max_files": 1,
                "remove_silence": False,
            },
        ),
        "create_rough_cut_plan_file",
    )
    timeline = _assert_ok(
        _call("create_timeline_from_rough_cut_plan", {"plan_file": plan["plan_file"]}),
        "create_timeline_from_rough_cut_plan",
    )
    saved = _assert_ok(
        _call(
            "save_timeline",
            {"timeline": timeline["timeline"], "output_directory": str(tmp_path), "name": "mlt_timeline"},
        ),
        "save_timeline",
    )
    return prepared["working_project"], saved["timeline_file"]


def _apply_with_check_mlt(working_project: str, timeline_file: str, tmp_path: Path, check_mlt: bool) -> dict[str, object]:
    return _call(
        "apply_timeline_to_working_project",
        {
            "working_project": working_project,
            "timeline_file": timeline_file,
            "output_directory": str(tmp_path),
            "check_mlt": check_mlt,
        },
    )


def test_apply_timeline_check_mlt_loaded(monkeypatch, tmp_path: Path) -> None:
    working_project, timeline_file = _prepare_working_copy_and_timeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": True,
            "checks": {"mlt_load": {"checked": True, "valid": True, "status": "loaded", "returncode": 0}},
        },
    )

    result = _apply_with_check_mlt(working_project, timeline_file, tmp_path, check_mlt=True)

    assert result["success"] is True
    assert result["mlt_load"]["valid"] is True
    assert result["mlt_load"]["status"] == "loaded"


def test_apply_timeline_check_mlt_failed(monkeypatch, tmp_path: Path) -> None:
    working_project, timeline_file = _prepare_working_copy_and_timeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": False,
            "checks": {"mlt_load": {"checked": True, "valid": False, "status": "failed", "returncode": 1}},
        },
    )

    result = _apply_with_check_mlt(working_project, timeline_file, tmp_path, check_mlt=True)

    assert result["success"] is False
    assert result["error"] == "MLT_ERROR"
    assert result["operation"] == "apply_timeline_to_working_project"
    assert result["warnings"] == []


def test_apply_timeline_check_mlt_unavailable(monkeypatch, tmp_path: Path) -> None:
    working_project, timeline_file = _prepare_working_copy_and_timeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": True,
            "checks": {
                "mlt_load": {
                    "checked": True,
                    "valid": None,
                    "status": "unavailable",
                    "error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
                }
            },
        },
    )

    result = _apply_with_check_mlt(working_project, timeline_file, tmp_path, check_mlt=True)

    assert result["success"] is True
    assert result["mlt_load"]["valid"] is None
    assert isinstance(result["warnings"], list)
    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert isinstance(warning, dict)
    assert warning["code"] == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"
    assert isinstance(warning["message"], str) and warning["message"]


def test_apply_timeline_check_mlt_false_skips_validate(monkeypatch, tmp_path: Path) -> None:
    working_project, timeline_file = _prepare_working_copy_and_timeline(monkeypatch, tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: calls.append(project) or {
            "success": True,
            "valid": True,
            "checks": {"mlt_load": {"checked": True, "valid": True, "status": "loaded"}},
        },
    )

    result = _apply_with_check_mlt(working_project, timeline_file, tmp_path, check_mlt=False)

    assert result["success"] is True
    assert calls == []


_ORCH_EDITS = [
    {"operation": "trim", "clip_id": "chain2_v", "source_out": 2.0},
    {"operation": "trim", "clip_id": "chain0_a", "source_out": 2.0},
    {"operation": "insert_gap", "position": 2.0, "duration": 0.5},
    {"operation": "split", "clip_id": "chain3_v", "split_at": 4.0},
]


def _prepare_working_copy(monkeypatch, tmp_path: Path) -> str:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": str(SOURCE_PROJECT),
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    return prepared["working_project"]


def _orch_args(working_project: str, tmp_path: Path, **overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "working_project": working_project,
        "edits": _ORCH_EDITS,
        "output_directory": str(tmp_path),
    }
    arguments.update(overrides)
    return arguments


def test_apply_edits_to_working_project_dry_run(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    working_copy_hash = _sha256(Path(working_project))

    result = _assert_ok(
        _call("apply_edits_to_working_project", _orch_args(working_project, tmp_path, dry_run=True)),
        "apply_edits_to_working_project",
    )

    assert result["dry_run"] is True
    assert "output_project" not in result
    assert "plan_timeline" in result
    assert len(result["plan_timeline"]["clips"]) >= 4
    assert not list(tmp_path.glob("*edited*.kdenlive"))
    assert result["timeline_source"] == "kdenlive_reverse_adapter"
    assert any(warning.get("code") == "TIMELINE_LOADED_FROM_KDENLIVE" for warning in result["warnings"])
    assert not any(warning.get("code") == "TIMELINE_RECONSTRUCTED_FROM_BIN" for warning in result["warnings"])
    assert _sha256(Path(working_project)) == working_copy_hash


def test_apply_edits_to_working_project_dry_run_does_not_block_real_run(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)

    dry = _assert_ok(
        _call("apply_edits_to_working_project", _orch_args(working_project, tmp_path, dry_run=True)),
        "apply_edits_to_working_project",
    )
    assert dry["dry_run"] is True

    real = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(working_project, tmp_path, dry_run=False, name="after_dry_run"),
        ),
        "apply_edits_to_working_project",
    )

    assert real["success"] is True
    output = Path(real["output_project"])
    assert output.exists()
    ET.parse(output)


def test_apply_edits_to_working_project_real_flow(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    working_copy_hash = _sha256(Path(working_project))

    result = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(working_project, tmp_path, dry_run=False, name="orchestrated"),
        ),
        "apply_edits_to_working_project",
    )

    output = Path(result["output_project"])
    assert output.exists()
    ET.parse(output)
    assert result["inspection_summary"]["timeline_clip_count"] >= 4
    assert result["timeline_source"] == "kdenlive_reverse_adapter"
    assert any(warning.get("code") == "TIMELINE_LOADED_FROM_KDENLIVE" for warning in result["warnings"])
    assert not any(warning.get("code") == "TIMELINE_RECONSTRUCTED_FROM_BIN" for warning in result["warnings"])
    assert _sha256(Path(working_project)) == working_copy_hash


def test_apply_edits_to_working_project_reverse_adapter_trims_linked_audio(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)

    result = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(
                working_project,
                tmp_path,
                dry_run=True,
                edits=[{"operation": "trim", "clip_id": "chain2_v", "source_out": 2.0}],
            ),
        ),
        "apply_edits_to_working_project",
    )

    assert result["timeline_source"] == "kdenlive_reverse_adapter"
    clips = {clip["id"]: clip for clip in result["plan_timeline"]["clips"]}
    assert clips["chain2_v"]["source_out"] == 2.0
    assert clips["chain0_a"]["source_out"] == 2.0


def test_export_edit_export_roundtrip_via_mcp(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    source_hash = _sha256(SOURCE_PROJECT)
    media_hashes = {path.name: _sha256(path) for path in (RECON_DIR / "sample1.mp4", RECON_DIR / "sample_vertical.mp4")}

    exported = _assert_ok(
        _call(
            "export_kdenlive_timeline",
            {
                "project": str(SOURCE_PROJECT),
                "output_directory": str(tmp_path),
                "name": "roundtrip_base",
            },
        ),
        "export_kdenlive_timeline",
    )
    timeline_file = exported["timeline_file"]

    edited = _assert_ok(
        _call(
            "apply_timeline_edits",
            {
                "timeline_file": timeline_file,
                "edits": [
                    {"operation": "trim", "clip_id": "chain2_v", "source_out": 2.0},
                    {"operation": "insert_gap", "position": 2.0, "duration": 0.5},
                    {"operation": "split", "clip_id": "chain3_v", "split_at": 4.0},
                ],
                "output_directory": str(tmp_path),
                "name": "roundtrip_edited",
                "dry_run": False,
            },
        ),
        "apply_timeline_edits",
    )
    edited_timeline_file = edited["timeline_file"]

    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": str(SOURCE_PROJECT),
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )
    working_project = prepared["working_project"]
    working_copy_hash = _sha256(Path(working_project))

    applied = _assert_ok(
        _call(
            "apply_timeline_to_working_project",
            {
                "working_project": working_project,
                "timeline_file": edited_timeline_file,
                "output_directory": str(tmp_path),
                "name": "roundtrip_output",
            },
        ),
        "apply_timeline_to_working_project",
    )
    output_project = Path(applied["output_project"])

    assert output_project.exists()
    ET.parse(output_project)

    validation = _assert_ok(_call("validate_project", {"project": str(output_project)}), "validate_project")
    assert validation["valid"] is True
    assert validation["checks"]["media_references"]["missing_media_count"] == 0

    inspection = _call("inspect_project", {"project": str(output_project)})
    assert inspection["success"] is True
    assert all(item["resource_exists"] for item in inspection["data"]["bin"]["media"])

    assert {path.name: _sha256(path) for path in (RECON_DIR / "sample1.mp4", RECON_DIR / "sample_vertical.mp4")} == media_hashes
    assert _sha256(SOURCE_PROJECT) == source_hash
    assert _sha256(Path(working_project)) == working_copy_hash


def test_apply_edits_to_working_project_falls_back_for_transition_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    prepared = _assert_ok(
        _call(
            "prepare_working_project",
            {
                "project": str(RECON_DIR / "manual_transition_dissolve.kdenlive"),
                "output_directory": str(tmp_path),
                "lock_directory": str(tmp_path / "locks"),
                "owner": "agent",
            },
        ),
        "prepare_working_project",
    )

    result = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(
                prepared["working_project"],
                tmp_path,
                dry_run=True,
                edits=[{"operation": "trim", "clip_id": "clip_001_v", "source_out": 2.0}],
            ),
        ),
        "apply_edits_to_working_project",
    )

    assert result["timeline_source"] == "project_bin_reconstruction"
    assert any(warning.get("code") == "TIMELINE_RECONSTRUCTED_FROM_BIN" for warning in result["warnings"])


def test_apply_edits_to_working_project_rejects_invalid_project(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    invalid = tmp_path / "broken.kdenlive"
    invalid.write_text("<mlt><unclosed>", encoding="utf-8")

    result = _call(
        "apply_edits_to_working_project",
        {"working_project": str(invalid), "edits": [{"operation": "trim", "clip_id": "chain2_v", "source_out": 2.0}]},
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_PROJECT"
    assert result["operation"] == "apply_edits_to_working_project"


def test_apply_edits_to_working_project_rejects_existing_output(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    output = tmp_path / "orchestrated_existing.kdenlive"
    output.write_bytes(b"existing")

    result = _call(
        "apply_edits_to_working_project",
        _orch_args(working_project, tmp_path, dry_run=False, name="orchestrated_existing"),
    )

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"existing"


def test_apply_edits_to_working_project_invalid_edit(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)

    result = _call(
        "apply_edits_to_working_project",
        _orch_args(working_project, tmp_path, dry_run=False, edits=[{"operation": "trim", "clip_id": "nope", "source_out": 1.0}]),
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_CLIP"
    assert result["operation"] == "apply_edits_to_working_project"
    assert isinstance(result["warnings"], list)


def test_apply_edits_to_working_project_check_mlt_loaded(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": True,
            "checks": {"mlt_load": {"checked": True, "valid": True, "status": "loaded", "returncode": 0}},
        },
    )

    result = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(working_project, tmp_path, dry_run=False, name="orchestrated_mlt_loaded", check_mlt=True),
        ),
        "apply_edits_to_working_project",
    )

    assert result["mlt_load"]["valid"] is True


def test_apply_edits_to_working_project_check_mlt_failed(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": False,
            "checks": {"mlt_load": {"checked": True, "valid": False, "status": "failed", "returncode": 1}},
        },
    )

    result = _call(
        "apply_edits_to_working_project",
        _orch_args(working_project, tmp_path, dry_run=False, name="orchestrated_mlt_failed", check_mlt=True),
    )

    assert result["success"] is False
    assert result["error"] == "MLT_ERROR"
    assert result["operation"] == "apply_edits_to_working_project"
    assert result["warnings"] == []


def test_apply_edits_to_working_project_check_mlt_unavailable(monkeypatch, tmp_path: Path) -> None:
    working_project = _prepare_working_copy(monkeypatch, tmp_path)
    monkeypatch.setattr(
        project_tools,
        "validate_project",
        lambda project, check_mlt=False: {
            "success": True,
            "valid": True,
            "checks": {
                "mlt_load": {
                    "checked": True,
                    "valid": None,
                    "status": "unavailable",
                    "error": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
                }
            },
        },
    )

    result = _assert_ok(
        _call(
            "apply_edits_to_working_project",
            _orch_args(working_project, tmp_path, dry_run=False, name="orchestrated_mlt_unavailable", check_mlt=True),
        ),
        "apply_edits_to_working_project",
    )

    assert result["mlt_load"]["valid"] is None
    assert any("FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX" in warning.get("code", "") for warning in result["warnings"])


@pytest.mark.skip(
    reason="No MCP tool edits a .kdenlive working copy IN PLACE. apply_timeline_to_working_project "
    "applies a timeline to a working copy and writes a new derived project (copy-on-write). "
    "True in-place editing of the working copy file itself remains a pending SHOULD."
)
def test_direct_kdenlive_working_copy_edit_is_pending() -> None:
    """Gap: direct in-place editing of a .kdenlive working copy is not implemented."""
