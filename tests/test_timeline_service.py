from __future__ import annotations

from pathlib import Path

import pytest

from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument
from kdenlive_mcp.services import timeline_service
from kdenlive_mcp.tools import rough_cut_tools, timeline_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"


def _create_plan_file(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    result = rough_cut_tools.create_rough_cut_plan_file(
        folder=str(RECON_DIR),
        output_directory=str(tmp_path),
        name="rough",
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )
    assert result["success"] is True
    return Path(result["plan_file"])


def test_create_timeline_from_rough_cut_plan(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)

    result = timeline_tools.create_timeline_from_rough_cut_plan(
        plan_file=str(plan_file),
        fps=30,
        width=1080,
        height=1920,
    )

    assert result["success"] is True
    assert result["operation"] == "create_timeline_from_rough_cut_plan"
    assert result["summary"] == {
        "track_count": 2,
        "clip_count": 4,
        "duration": 4.0,
        "fps": 30.0,
        "width": 1080,
        "height": 1920,
    }
    timeline = result["timeline"]
    assert timeline["kind"] == "kdenlive_mcp_timeline"
    assert [track["id"] for track in timeline["tracks"]] == ["track_v1", "track_a1"]
    assert timeline["clips"][0]["id"] == "clip_001_v"
    assert timeline["clips"][0]["linked_clip_id"] == "clip_001_a"
    assert timeline["clips"][1]["linked_clip_id"] == "clip_001_v"


def test_save_and_inspect_timeline(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))

    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="Vlog Timeline",
    )

    assert saved["success"] is True
    timeline_file = Path(saved["timeline_file"])
    assert timeline_file.exists()
    assert timeline_file.name == "Vlog_Timeline.timeline.json"

    inspected = timeline_tools.inspect_timeline(str(timeline_file))
    assert inspected["success"] is True
    assert inspected["summary"]["clip_count"] == 4
    assert inspected["data"]["clips"][0]["track_id"] == "track_v1"


def test_validate_timeline_accepts_generated_timeline(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="valid",
    )

    result = timeline_tools.validate_timeline(str(saved["timeline_file"]))

    assert result["success"] is True
    assert result["valid"] is True
    assert result["issue_count"] == 0


def test_validate_timeline_detects_overlap(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    timeline = created["timeline"]
    timeline["clips"][2]["timeline_in"] = 2.5
    timeline["clips"][2]["timeline_out"] = 3.5
    timeline["clips"][3]["timeline_in"] = 2.5
    timeline["clips"][3]["timeline_out"] = 3.5
    document = TimelineDocument.model_validate(timeline)
    path = timeline_service.timeline_path_for(tmp_path, "overlap")
    timeline_service.save_timeline_document(path, document)

    result = timeline_tools.validate_timeline(str(path), check_media_exists=False)

    assert result["success"] is True
    assert result["valid"] is False
    assert {issue["code"] for issue in result["issues"]} == {"TIMELINE_OVERLAP"}


def test_validate_timeline_detects_duration_mismatch(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    timeline = created["timeline"]
    timeline["clips"][0]["timeline_out"] = 2.5
    document = TimelineDocument.model_validate(timeline)
    path = timeline_service.timeline_path_for(tmp_path, "duration_mismatch")
    timeline_service.save_timeline_document(path, document)

    result = timeline_tools.validate_timeline(str(path), check_media_exists=False)

    assert result["success"] is True
    assert result["valid"] is False
    assert "DURATION_MISMATCH" in {issue["code"] for issue in result["issues"]}


def test_validate_timeline_detects_linked_clip_mismatch(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    timeline = created["timeline"]
    timeline["clips"][1]["source_out"] = 2.0
    document = TimelineDocument.model_validate(timeline)
    path = timeline_service.timeline_path_for(tmp_path, "linked_mismatch")
    timeline_service.save_timeline_document(path, document)

    result = timeline_tools.validate_timeline(str(path), check_media_exists=False)

    assert result["success"] is True
    assert result["valid"] is False
    assert "LINKED_CLIP_MISMATCH" in {issue["code"] for issue in result["issues"]}


def test_validate_timeline_detects_media_offline(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    timeline = TimelineDocument(
        tracks=[
            {"id": "track_v1", "type": "video", "name": "Video 1"},
        ],
        clips=[
            {
                "id": "clip_001_v",
                "track_id": "track_v1",
                "media_id": "media_missing",
                "media": str(tmp_path / "missing.mp4"),
                "source_in": 0.0,
                "source_out": 1.0,
                "timeline_in": 0.0,
                "timeline_out": 1.0,
            }
        ],
    )
    path = timeline_service.timeline_path_for(tmp_path, "offline")
    timeline_service.save_timeline_document(path, timeline)

    result = timeline_tools.validate_timeline(str(path), check_media_exists=True)

    assert result["success"] is True
    assert result["valid"] is False
    assert result["issues"][0]["code"] == "MEDIA_OFFLINE"


def test_save_timeline_refuses_existing_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))

    first = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="existing")
    second = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="existing")

    assert first["success"] is True
    assert second["success"] is False
    assert second["error"] == "OUTPUT_EXISTS"


def test_save_timeline_requires_output_allowlist(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path / "allowed"))

    result = timeline_tools.save_timeline(
        timeline={"kind": "kdenlive_mcp_timeline", "tracks": [], "clips": []},
        output_directory=str(tmp_path / "denied"),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_timeline_document_rejects_unknown_track() -> None:
    with pytest.raises(ValueError, match="unknown track"):
        TimelineDocument(
            tracks=[],
            clips=[
                TimelineClip(
                    id="clip_001_v",
                    track_id="missing_track",
                    media_id="media_a",
                    media="/tmp/a.mp4",
                    source_in=0.0,
                    source_out=1.0,
                    timeline_in=0.0,
                    timeline_out=1.0,
                )
            ],
        )
