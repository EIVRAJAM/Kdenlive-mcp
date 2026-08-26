from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

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


def _create_saved_timeline(monkeypatch, tmp_path: Path, name: str = "timeline") -> dict[str, object]:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name=name)
    assert saved["success"] is True
    return saved


def _export_project(monkeypatch, tmp_path: Path, timeline_file: str, name: str) -> dict[str, object]:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    result = timeline_tools.export_timeline_to_kdenlive_template(
        timeline_file=timeline_file,
        template_project=str(RECON_DIR / "manual_empty_vertical.kdenlive"),
        output_directory=str(tmp_path),
        name=name,
    )
    assert result["success"] is True
    return result


def _timeline_clips_from_exported_project(project: str) -> list[dict[str, object]]:
    inspection = timeline_service.KdenliveProjectAdapter().inspect(project)
    active_sequence = next(
        sequence for sequence in inspection["sequences"] if sequence["id"] == inspection["active_sequence_id"]
    )
    return active_sequence["timeline_clips"]


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
        "marker_count": 2,
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
    assert timeline["markers"] == [
        {"id": "marker_001", "comment": "rough_001", "position": 0.0, "duration": 3.0, "type": 0},
        {"id": "marker_002", "comment": "rough_002", "position": 3.0, "duration": 1.0, "type": 0},
    ]


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
    assert inspected["summary"]["marker_count"] == 2
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


def test_create_timeline_track_writes_copy(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="track_create_source")

    result = timeline_tools.create_timeline_track(
        timeline_file=str(saved["timeline_file"]),
        track_type="video",
        name="B-roll",
        output_directory=str(tmp_path),
        output_name="track_create_result",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["after"]["track"] == {
        "id": "track_v2",
        "type": "video",
        "name": "B-roll",
        "locked": False,
        "muted": False,
    }
    inspected = timeline_tools.inspect_timeline(str(result["timeline_file"]))
    assert inspected["summary"]["track_count"] == 3
    assert [track["id"] for track in inspected["data"]["tracks"]] == ["track_v1", "track_a1", "track_v2"]


def test_update_timeline_track_writes_copy(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="track_update_source")

    result = timeline_tools.update_timeline_track(
        timeline_file=str(saved["timeline_file"]),
        track_id="track_a1",
        name="Voice",
        locked=True,
        muted=True,
        output_directory=str(tmp_path),
        output_name="track_update_result",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["before"]["track"]["name"] == "Audio 1"
    assert result["after"]["track"]["name"] == "Voice"
    assert result["after"]["track"]["locked"] is True
    assert result["after"]["track"]["muted"] is True


def test_remove_timeline_track_refuses_track_with_clips_by_default(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="track_remove_refuse_source")

    result = timeline_tools.remove_timeline_track(
        timeline_file=str(saved["timeline_file"]),
        track_id="track_a1",
        output_directory=str(tmp_path),
        output_name="track_remove_refuse_result",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["error"] == "TRACK_NOT_EMPTY"
    assert result["clip_count"] == 2
    assert not (tmp_path / "track_remove_refuse_result.timeline.json").exists()


def test_remove_timeline_track_with_clips_clears_remaining_links(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="track_remove_source")

    result = timeline_tools.remove_timeline_track(
        timeline_file=str(saved["timeline_file"]),
        track_id="track_a1",
        remove_clips=True,
        output_directory=str(tmp_path),
        output_name="track_remove_result",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["after"]["removed_track_id"] == "track_a1"
    assert result["after"]["removed_clip_count"] == 2
    inspected = timeline_tools.inspect_timeline(str(result["timeline_file"]))
    assert inspected["summary"]["track_count"] == 1
    assert inspected["summary"]["clip_count"] == 2
    assert all(clip.get("linked_clip_id") is None for clip in inspected["data"]["clips"])


def test_trim_timeline_clip_dry_run_does_not_write(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="trim_source")
    timeline_file = Path(saved["timeline_file"])
    original = timeline_file.read_text(encoding="utf-8")

    result = timeline_tools.trim_timeline_clip(
        timeline_file=str(timeline_file),
        clip_id="clip_001_v",
        source_out=2.0,
        output_directory=str(tmp_path),
        name="trimmed",
        dry_run=True,
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["timeline_file"] is None
    assert result["would_write"].endswith("trimmed.timeline.json")
    assert not (tmp_path / "trimmed.timeline.json").exists()
    assert timeline_file.read_text(encoding="utf-8") == original
    assert result["after"]["clips"]["clip_001_v"]["timeline_out"] == 2.0
    assert result["after"]["clips"]["clip_001_a"]["timeline_out"] == 2.0


def test_trim_timeline_clip_writes_copy_with_linked_clip(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="trim_write_source")

    result = timeline_tools.trim_timeline_clip(
        timeline_file=saved["timeline_file"],
        clip_id="clip_001_v",
        source_in=0.5,
        source_out=2.5,
        output_directory=str(tmp_path),
        name="trim_write_result",
        dry_run=False,
    )

    assert result["success"] is True
    assert Path(result["timeline_file"]).name == "trim_write_result.timeline.json"
    inspected = timeline_tools.inspect_timeline(result["timeline_file"])
    clips = {clip["id"]: clip for clip in inspected["data"]["clips"]}
    assert clips["clip_001_v"]["source_in"] == 0.5
    assert clips["clip_001_v"]["source_out"] == 2.5
    assert clips["clip_001_a"]["source_in"] == 0.5
    assert clips["clip_001_a"]["source_out"] == 2.5
    assert inspected["summary"]["clip_count"] == 4


def test_move_timeline_clip_writes_copy_and_moves_marker(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="move_source")

    result = timeline_tools.move_timeline_clip(
        timeline_file=saved["timeline_file"],
        clip_id="clip_002_v",
        timeline_in=4.0,
        output_directory=str(tmp_path),
        name="move_result",
        dry_run=False,
    )

    assert result["success"] is True
    inspected = timeline_tools.inspect_timeline(result["timeline_file"])
    clips = {clip["id"]: clip for clip in inspected["data"]["clips"]}
    markers = {marker["id"]: marker for marker in inspected["data"]["markers"]}
    assert clips["clip_002_v"]["timeline_in"] == 4.0
    assert clips["clip_002_v"]["timeline_out"] == 5.0
    assert clips["clip_002_a"]["timeline_in"] == 4.0
    assert markers["marker_002"]["position"] == 4.0


def test_move_timeline_clip_reports_overlap(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="move_overlap_source")

    result = timeline_tools.move_timeline_clip(
        timeline_file=saved["timeline_file"],
        clip_id="clip_002_v",
        timeline_in=2.5,
        output_directory=str(tmp_path),
        name="move_overlap_result",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_TIMELINE"
    assert "TIMELINE_OVERLAP" in {issue["code"] for issue in result["validation"]["issues"]}
    assert not (tmp_path / "move_overlap_result.timeline.json").exists()


def test_split_timeline_clip_writes_copy_with_linked_halves(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="split_source")

    result = timeline_tools.split_timeline_clip(
        timeline_file=saved["timeline_file"],
        clip_id="clip_001_v",
        split_at=1.25,
        output_directory=str(tmp_path),
        name="split_result",
        dry_run=False,
    )

    assert result["success"] is True
    inspected = timeline_tools.inspect_timeline(result["timeline_file"])
    clips = {clip["id"]: clip for clip in inspected["data"]["clips"]}
    assert inspected["summary"]["clip_count"] == 6
    assert clips["clip_001_v_part1"]["linked_clip_id"] == "clip_001_a_part1"
    assert clips["clip_001_a_part1"]["linked_clip_id"] == "clip_001_v_part1"
    assert clips["clip_001_v_part2"]["linked_clip_id"] == "clip_001_a_part2"
    assert clips["clip_001_v_part1"]["timeline_out"] == 1.25
    assert clips["clip_001_v_part2"]["timeline_in"] == 1.25
    assert clips["clip_001_v_part1"]["source_out"] == 1.25
    assert clips["clip_001_v_part2"]["source_in"] == 1.25


def test_split_timeline_clip_rejects_out_of_range(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(created["timeline"], str(tmp_path), name="split_invalid_source")

    result = timeline_tools.split_timeline_clip(
        timeline_file=saved["timeline_file"],
        clip_id="clip_001_v",
        split_at=3.0,
        output_directory=str(tmp_path),
        name="split_invalid_result",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_TIMECODE"
    assert not (tmp_path / "split_invalid_result.timeline.json").exists()


def test_apply_timeline_edits_writes_single_copy(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="batch_source")

    result = timeline_tools.apply_timeline_edits(
        timeline_file=str(saved["timeline_file"]),
        edits=[
            {"operation": "trim", "clip_id": "clip_001_v", "source_out": 2.0},
            {"operation": "split", "clip_id": "clip_001_v", "split_at": 1.0},
            {"operation": "move", "clip_id": "clip_002_v", "timeline_in": 4.0},
        ],
        output_directory=str(tmp_path),
        name="batch_result",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["edit_count"] == 3
    assert [step["operation"] for step in result["steps"]] == ["trim", "split", "move"]
    assert Path(result["timeline_file"]).name == "batch_result.timeline.json"

    inspected = timeline_tools.inspect_timeline(str(result["timeline_file"]))
    assert inspected["summary"]["clip_count"] == 6
    clips = {clip["id"]: clip for clip in inspected["data"]["clips"]}
    assert clips["clip_001_v_part1"]["timeline_out"] == 1.0
    assert clips["clip_001_v_part2"]["timeline_in"] == 1.0
    assert clips["clip_002_v"]["timeline_in"] == 4.0


def test_apply_timeline_edits_dry_run_does_not_write(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="batch_dry_run_source")

    result = timeline_tools.apply_timeline_edits(
        timeline_file=str(saved["timeline_file"]),
        edits=[{"operation": "trim", "clip_id": "clip_001_v", "source_out": 2.0}],
        output_directory=str(tmp_path),
        name="batch_dry_run_result",
        dry_run=True,
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["timeline_file"] is None
    assert result["edit_count"] == 1
    assert not (tmp_path / "batch_dry_run_result.timeline.json").exists()


def test_apply_timeline_edits_refuses_invalid_final_timeline(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="batch_invalid_source")

    result = timeline_tools.apply_timeline_edits(
        timeline_file=str(saved["timeline_file"]),
        edits=[{"operation": "move", "clip_id": "clip_002_v", "timeline_in": 2.5}],
        output_directory=str(tmp_path),
        name="batch_invalid_result",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_TIMELINE"
    assert result["edit_count"] == 1
    assert "TIMELINE_OVERLAP" in {issue["code"] for issue in result["validation"]["issues"]}
    assert not (tmp_path / "batch_invalid_result.timeline.json").exists()


def test_apply_timeline_edits_export_to_kdenlive_template(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="batch_export_source")
    batch = timeline_tools.apply_timeline_edits(
        timeline_file=str(saved["timeline_file"]),
        edits=[
            {"operation": "trim", "clip_id": "clip_001_v", "source_out": 2.0},
            {"operation": "split", "clip_id": "clip_001_v", "split_at": 1.0},
            {"operation": "move", "clip_id": "clip_002_v", "timeline_in": 4.0},
        ],
        output_directory=str(tmp_path),
        name="batch_export_timeline",
        dry_run=False,
    )
    assert batch["success"] is True

    exported = _export_project(monkeypatch, tmp_path, str(batch["timeline_file"]), "batch_export_project")

    clips = _timeline_clips_from_exported_project(str(exported["project"]))
    assert exported["inspection_summary"]["timeline_clip_count"] == 6
    assert sorted(clip["start_frame"] for clip in clips if clip["media_id"] == "5") == [120, 120]
    assert {clip["duration_frames"] for clip in clips if clip["media_id"] == "4"} == {30, 30}


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


def test_export_timeline_to_mlt_xml(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="exportable",
    )

    result = timeline_tools.export_timeline_to_mlt_xml(
        timeline_file=str(saved["timeline_file"]),
        output_directory=str(tmp_path),
        name="draft",
    )

    assert result["success"] is True
    assert result["operation"] == "export_timeline_to_mlt_xml"
    assert result["kdenlive_project"] is False
    assert Path(result["mlt_xml"]).name == "draft.mlt.xml"
    root = ET.parse(result["mlt_xml"]).getroot()
    assert root.tag == "mlt"
    assert root.find("tractor[@id='main_tractor']") is not None


def test_export_timeline_to_mlt_xml_refuses_invalid_timeline(monkeypatch, tmp_path: Path) -> None:
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    timeline = created["timeline"]
    timeline["clips"][0]["timeline_out"] = 2.5
    document = TimelineDocument.model_validate(timeline)
    path = timeline_service.timeline_path_for(tmp_path, "invalid_export")
    timeline_service.save_timeline_document(path, document)

    result = timeline_tools.export_timeline_to_mlt_xml(
        timeline_file=str(path),
        output_directory=str(tmp_path),
        name="invalid",
        check_media_exists=False,
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_TIMELINE"
    assert result["validation"]["valid"] is False


def test_export_timeline_to_kdenlive_template(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="exportable_project",
    )

    result = timeline_tools.export_timeline_to_kdenlive_template(
        timeline_file=str(saved["timeline_file"]),
        template_project=str(RECON_DIR / "manual_empty_vertical.kdenlive"),
        output_directory=str(tmp_path),
        name="draft_project",
    )

    assert result["success"] is True
    assert result["operation"] == "export_timeline_to_kdenlive_template"
    assert Path(result["project"]).name == "draft_project.kdenlive"
    assert result["inspection_summary"]["bin_media_count"] == 2
    assert result["inspection_summary"]["timeline_clip_count"] == 4
    assert result["inspection_summary"]["marker_count"] == 2
    assert result["inspection_summary"]["guide_count"] == 2
    assert result["inspection_summary"]["missing_media_count"] == 0

    root = ET.parse(result["project"]).getroot()
    sequence = root.find("tractor[@id='tractor4']")
    assert sequence is not None
    props = {prop.attrib["name"]: prop.text or "" for prop in sequence.findall("property")}
    assert '"comment": "rough_001"' in props["kdenlive:sequenceproperties.guides"]
    assert '"comment": "rough_002"' in props["kdenlive:markers"]


def test_export_trimmed_timeline_to_kdenlive_template(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="trim_export_source")
    trimmed = timeline_tools.trim_timeline_clip(
        timeline_file=str(saved["timeline_file"]),
        clip_id="clip_001_v",
        source_out=2.0,
        output_directory=str(tmp_path),
        name="trim_export_timeline",
        dry_run=False,
    )
    assert trimmed["success"] is True

    exported = _export_project(monkeypatch, tmp_path, str(trimmed["timeline_file"]), "trim_export_project")

    clips = _timeline_clips_from_exported_project(str(exported["project"]))
    first_video = next(clip for clip in clips if clip["media_id"] == "4" and clip["start_frame"] == 0)
    assert first_video["in_frame"] == 0
    assert first_video["out_frame"] == 59
    assert first_video["duration_frames"] == 60
    assert exported["inspection_summary"]["timeline_clip_count"] == 4


def test_export_moved_timeline_to_kdenlive_template_preserves_gap(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="move_export_source")
    moved = timeline_tools.move_timeline_clip(
        timeline_file=str(saved["timeline_file"]),
        clip_id="clip_002_v",
        timeline_in=4.0,
        output_directory=str(tmp_path),
        name="move_export_timeline",
        dry_run=False,
    )
    assert moved["success"] is True

    exported = _export_project(monkeypatch, tmp_path, str(moved["timeline_file"]), "move_export_project")

    clips = _timeline_clips_from_exported_project(str(exported["project"]))
    second_clip_starts = sorted(clip["start_frame"] for clip in clips if clip["media_id"] == "5")
    assert second_clip_starts == [120, 120]
    assert exported["inspection_summary"]["guide_count"] == 2


def test_export_split_timeline_to_kdenlive_template(monkeypatch, tmp_path: Path) -> None:
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="split_export_source")
    split = timeline_tools.split_timeline_clip(
        timeline_file=str(saved["timeline_file"]),
        clip_id="clip_001_v",
        split_at=1.25,
        output_directory=str(tmp_path),
        name="split_export_timeline",
        dry_run=False,
    )
    assert split["success"] is True

    exported = _export_project(monkeypatch, tmp_path, str(split["timeline_file"]), "split_export_project")

    clips = _timeline_clips_from_exported_project(str(exported["project"]))
    assert exported["inspection_summary"]["timeline_clip_count"] == 6
    first_media_clips = sorted(
        [clip for clip in clips if clip["media_id"] == "4"],
        key=lambda clip: (clip["start_frame"], clip["playlist_id"]),
    )
    assert {clip["duration_frames"] for clip in first_media_clips} == {38, 52}
    assert {clip["start_frame"] for clip in first_media_clips} == {0, 38}


def test_export_timeline_to_kdenlive_template_maps_extra_video_track(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="multi_track_source")
    inspected = timeline_tools.inspect_timeline(str(saved["timeline_file"]))
    timeline = inspected["data"]
    timeline["tracks"].append({"id": "track_v2", "type": "video", "name": "B-roll"})
    first_video = next(clip for clip in timeline["clips"] if clip["id"] == "clip_001_v")
    timeline["clips"].append(
        {
            **first_video,
            "id": "clip_broll_001",
            "track_id": "track_v2",
            "source_out": 1.0,
            "timeline_out": 1.0,
            "linked_clip_id": None,
            "reason": "overlay",
        }
    )
    path = timeline_service.timeline_path_for(tmp_path, "multi_track_timeline")
    timeline_service.save_timeline_document(path, TimelineDocument.model_validate(timeline))

    result = timeline_tools.export_timeline_to_kdenlive_template(
        timeline_file=str(path),
        template_project=str(RECON_DIR / "manual_empty_vertical.kdenlive"),
        output_directory=str(tmp_path),
        name="multi_track_project",
    )

    assert result["success"] is True
    assert result["write_result"]["track_playlist_map"]["track_v1"] != result["write_result"]["track_playlist_map"]["track_v2"]
    assert result["inspection_summary"]["timeline_clip_count"] == 5
    clips = _timeline_clips_from_exported_project(str(result["project"]))
    extra_clip_playlist = result["write_result"]["track_playlist_map"]["track_v2"]
    assert any(clip["playlist_id"] == extra_clip_playlist for clip in clips)


def test_export_timeline_to_kdenlive_template_refuses_more_tracks_than_template(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    saved = _create_saved_timeline(monkeypatch, tmp_path, name="too_many_tracks_source")
    inspected = timeline_tools.inspect_timeline(str(saved["timeline_file"]))
    timeline = inspected["data"]
    for index in range(2, 7):
        timeline["tracks"].append({"id": f"track_v{index}", "type": "video", "name": f"Video {index}"})
    path = timeline_service.timeline_path_for(tmp_path, "too_many_tracks_timeline")
    timeline_service.save_timeline_document(path, TimelineDocument.model_validate(timeline))

    result = timeline_tools.export_timeline_to_kdenlive_template(
        timeline_file=str(path),
        template_project=str(RECON_DIR / "manual_empty_vertical.kdenlive"),
        output_directory=str(tmp_path),
        name="too_many_tracks_project",
    )

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_TIMELINE"
    assert "editable video playlists" in result["message"]
    assert not (tmp_path / "too_many_tracks_project.kdenlive").exists()


def test_export_timeline_to_kdenlive_template_detects_target_playlists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="custom_targets_timeline",
    )
    template_path = tmp_path / "custom_target_template.kdenlive"
    tree = ET.parse(RECON_DIR / "manual_empty_vertical.kdenlive")
    root = tree.getroot()
    root.find("playlist[@id='playlist0']").attrib["id"] = "audio_primary"
    root.find("playlist[@id='playlist6']").attrib["id"] = "video_primary"
    for track in root.findall(".//track"):
        if track.attrib.get("producer") == "playlist0":
            track.attrib["producer"] = "audio_primary"
        elif track.attrib.get("producer") == "playlist6":
            track.attrib["producer"] = "video_primary"
    tree.write(template_path, encoding="utf-8", xml_declaration=True)

    result = timeline_tools.export_timeline_to_kdenlive_template(
        timeline_file=str(saved["timeline_file"]),
        template_project=str(template_path),
        output_directory=str(tmp_path),
        name="custom_target_project",
    )

    assert result["success"] is True
    exported = ET.parse(result["project"]).getroot()
    audio_playlist = exported.find("playlist[@id='audio_primary']")
    video_playlist = exported.find("playlist[@id='video_primary']")
    assert audio_playlist is not None
    assert video_playlist is not None
    assert len(audio_playlist.findall("entry")) == 2
    assert len(video_playlist.findall("entry")) == 2
    assert exported.find("playlist[@id='playlist0']") is None
    assert exported.find("playlist[@id='playlist6']") is None


def test_export_timeline_to_kdenlive_template_refuses_existing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", f"{RECON_DIR}:{tmp_path}")
    plan_file = _create_plan_file(monkeypatch, tmp_path)
    created = timeline_tools.create_timeline_from_rough_cut_plan(plan_file=str(plan_file))
    saved = timeline_tools.save_timeline(
        timeline=created["timeline"],
        output_directory=str(tmp_path),
        name="existing_project_timeline",
    )
    kwargs = {
        "timeline_file": str(saved["timeline_file"]),
        "template_project": str(RECON_DIR / "manual_empty_vertical.kdenlive"),
        "output_directory": str(tmp_path),
        "name": "existing_project",
    }

    first = timeline_tools.export_timeline_to_kdenlive_template(**kwargs)
    second = timeline_tools.export_timeline_to_kdenlive_template(**kwargs)

    assert first["success"] is True
    assert second["success"] is False
    assert second["error"] == "OUTPUT_EXISTS"


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
