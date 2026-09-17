from pathlib import Path

import pytest

from kdenlive_mcp.adapters.commands import CommandResult
from kdenlive_mcp.adapters.kdenlive_xml import (
    KdenliveProjectAdapter,
    KdenliveProjectError,
    frame_to_kdenlive_timecode,
    parse_timecode_to_frames,
    seconds_to_kdenlive_in_timecode,
    seconds_to_kdenlive_out_timecode,
)
from kdenlive_mcp.domain.timeline import TimelineDocument
from kdenlive_mcp.server import handle_request
from kdenlive_mcp.services.timeline_service import load_timeline_document
from kdenlive_mcp.tools import project_tools


import json


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
TWO_CLIPS_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"
MARKER_PROJECT = RECON_DIR / "manual_trim_marker.kdenlive"


def _mcp_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
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


def test_parse_timecode_to_frames_for_kdenlive_milliseconds() -> None:
    assert parse_timecode_to_frames("00:00:00.000", 30) == 0
    assert parse_timecode_to_frames("00:00:02.967", 30) == 89
    assert parse_timecode_to_frames("00:00:05.967", 30) == 179


def test_kdenlive_timecode_helpers_use_inclusive_out_frames() -> None:
    assert frame_to_kdenlive_timecode(89, 30) == "00:00:02.967"
    assert seconds_to_kdenlive_in_timecode(3.0, 30) == "00:00:03.000"
    assert seconds_to_kdenlive_out_timecode(3.0, 30) == "00:00:02.967"


def test_inspect_project_extracts_profile_document_and_bin_media() -> None:
    data = KdenliveProjectAdapter().inspect(TWO_CLIPS_PROJECT)

    assert data["profile"]["width"] == 1080
    assert data["profile"]["height"] == 1920
    assert data["document"]["kdenlive_version"] == "26.04.3"
    assert data["document"]["profile"] == "vertical_hd_30"
    assert data["bin"]["media_count"] == 2
    assert {item["resource"] for item in data["bin"]["media"]} == {
        "sample1.mp4",
        "sample_vertical.mp4",
    }
    assert data["validation"]["missing_media_count"] == 0


def test_inspect_project_extracts_sequence_tracks_and_timeline_clips() -> None:
    data = KdenliveProjectAdapter().inspect(TWO_CLIPS_PROJECT)
    sequence = data["sequences"][0]

    assert data["active_sequence_id"] == "tractor4"
    assert sequence["name"] == "Secuencia 1"
    assert sequence["timeline_clip_count"] == 4

    audio_tracks = [track for track in sequence["tracks"] if track["kind"] == "audio"]
    video_tracks = [track for track in sequence["tracks"] if track["kind"] == "video"]

    assert len(audio_tracks) == 4
    assert len(video_tracks) == 4
    assert audio_tracks[0]["clip_count"] == 2
    assert video_tracks[-2]["clip_count"] == 2

    first_audio_clip = audio_tracks[0]["clips"][0]
    second_audio_clip = audio_tracks[0]["clips"][1]

    assert first_audio_clip["media_id"] == "4"
    assert first_audio_clip["start_frame"] == 0
    assert first_audio_clip["duration_frames"] == 90
    assert second_audio_clip["media_id"] == "5"
    assert second_audio_clip["start_frame"] == 90


def test_inspect_project_extracts_guides_and_markers() -> None:
    data = KdenliveProjectAdapter().inspect(MARKER_PROJECT)
    sequence = data["sequences"][0]

    assert sequence["guides"] == [{"comment": "hook", "duration": 75, "pos": 0, "type": 0}]
    assert sequence["markers"] == [{"comment": "hook", "duration": 75, "pos": 0, "type": 0}]


def test_inspect_project_tool_requires_allowed_project_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(tmp_path))

    result = project_tools.inspect_project(project=str(TWO_CLIPS_PROJECT))

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_inspect_project_tool_returns_structured_data(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))

    result = project_tools.inspect_project(project=str(TWO_CLIPS_PROJECT))

    assert result["success"] is True
    assert result["operation"] == "inspect_project"
    assert result["data"]["bin"]["media_count"] == 2


def test_validate_project_static_checks(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))

    result = project_tools.validate_project(project=str(TWO_CLIPS_PROJECT))

    assert result["success"] is True
    assert result["valid"] is True
    assert result["checks"]["xml_parse"]["valid"] is True
    assert result["checks"]["media_references"]["valid"] is True
    assert result["checks"]["mlt_load"]["checked"] is False
    assert result["summary"]["media_count"] == 2


def test_validate_project_with_mlt_success(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))

    def fake_run(command, timeout):
        return CommandResult(
            command=command,
            available=True,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(project_tools, "run_command", fake_run)

    result = project_tools.validate_project(project=str(TWO_CLIPS_PROJECT), check_mlt=True)

    assert result["success"] is True
    assert result["valid"] is True
    assert result["checks"]["mlt_load"]["checked"] is True
    assert result["checks"]["mlt_load"]["status"] == "loaded"


def test_validate_project_reports_flatpak_sandbox_without_marking_invalid(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))

    def fake_run(command, timeout):
        return CommandResult(
            command=command,
            available=True,
            returncode=1,
            stdout="",
            stderr="error: Unable to allocate instance id",
            error="Command failed",
        )

    monkeypatch.setattr(project_tools, "run_command", fake_run)

    result = project_tools.validate_project(project=str(TWO_CLIPS_PROJECT), check_mlt=True)

    assert result["success"] is True
    assert result["valid"] is True
    assert result["checks"]["mlt_load"]["status"] == "unavailable"
    assert result["checks"]["mlt_load"]["error"] == "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX"


def _timeline_summary(name: str) -> dict[str, object]:
    return KdenliveProjectAdapter().extract_timeline_summary(RECON_DIR / name)


def test_extract_timeline_summary_detects_trim() -> None:
    summary = _timeline_summary("manual_trimmed_clip.kdenlive")

    assert summary["active_sequence_id"] == "tractor4"
    assert summary["fps"] == 30.0
    video_clips = [clip for clip in summary["timeline_clips"] if clip["track_kind"] == "video"]
    assert any(clip["source_in_frames"] != 0 for clip in video_clips)


def test_extract_timeline_summary_detects_gaps() -> None:
    summary = _timeline_summary("manual_gap_timeline.kdenlive")

    assert len(summary["gaps"]) >= 2
    video_gaps = [gap for gap in summary["gaps"] if gap["track_kind"] == "video"]
    assert video_gaps and video_gaps[0]["duration_frames"] > 0


def test_extract_timeline_summary_detects_user_transition() -> None:
    summary = _timeline_summary("manual_transition_dissolve.kdenlive")

    user = [transition for transition in summary["user_transitions"] if transition["is_user"]]
    assert len(user) >= 1
    assert user[0]["mlt_service"] == "composite"
    assert user[0]["in"] is not None and user[0]["out"] is not None


def test_extract_timeline_summary_detects_clip_effect() -> None:
    summary = _timeline_summary("manual_basic_effect.kdenlive")

    assert any(effect["mlt_service"] == "qtblend" for effect in summary["clip_effects"])


def test_extract_timeline_summary_reports_proxy_media_ids() -> None:
    summary = _timeline_summary("proxy_fixture.kdenlive")

    assert summary["proxy_media_ids"] == ["4"]

    plain = _timeline_summary("manual_two_clips_timeline.kdenlive")
    assert plain["proxy_media_ids"] == []


def test_extract_timeline_summary_positions_accumulate_entries_and_blanks() -> None:
    gap_summary = _timeline_summary("manual_gap_timeline.kdenlive")
    base_summary = _timeline_summary("manual_two_clips_timeline.kdenlive")

    gap_video = [clip for clip in gap_summary["timeline_clips"] if clip["track_kind"] == "video"]
    base_video = [clip for clip in base_summary["timeline_clips"] if clip["track_kind"] == "video"]
    # The blank shifts the later clip forward; positions are accumulated from
    # entries and blanks, not taken from entry in/out (which are source ranges).
    gap_second_media = sorted([c for c in gap_video if c["producer"] == "chain3"], key=lambda c: c["position_frames"])[0]
    base_second_media = sorted([c for c in base_video if c["producer"] == "chain3"], key=lambda c: c["position_frames"])[0]
    assert gap_second_media["position_frames"] > base_second_media["position_frames"]
    assert gap_second_media["source_in"] == base_second_media["source_in"]


def test_extract_timeline_summary_does_not_classify_internal_added_as_user() -> None:
    for name in ("manual_two_clips_timeline", "manual_trimmed_clip", "manual_gap_timeline"):
        summary = _timeline_summary(f"{name}.kdenlive")

        for transition in summary["user_transitions"]:
            assert transition["is_user"] is False
        assert summary["clip_effects"] == []

    effect_summary = _timeline_summary("manual_basic_effect.kdenlive")
    assert effect_summary["clip_effects"]
    for effect in effect_summary["clip_effects"]:
        assert effect["mlt_service"] == "qtblend"  # only the user effect is present


def test_inspect_kdenlive_timeline_via_mcp(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")

    result = _mcp_call(
        "inspect_kdenlive_timeline",
        {"project": str(RECON_DIR / "manual_trimmed_clip.kdenlive")},
    )

    assert result["success"] is True
    assert result["operation"] == "inspect_kdenlive_timeline"
    assert result["summary"]["timeline_clips"]
    assert any(clip["source_in_frames"] != 0 for clip in result["summary"]["timeline_clips"])
    assert any(
        warning.get("code") == "TIMELINE_SUMMARY_HAS_INFERRED_FIELDS" for warning in result["warnings"]
    )


def test_inspect_kdenlive_timeline_rejects_outside_allowlist(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")

    result = _mcp_call("inspect_kdenlive_timeline", {"project": str(RECON_DIR / "manual_trimmed_clip.kdenlive")})

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_inspect_kdenlive_timeline_rejects_invalid_xml(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    invalid = tmp_path / "broken.kdenlive"
    invalid.write_text("<mlt><unclosed>", encoding="utf-8")

    result = _mcp_call("inspect_kdenlive_timeline", {"project": str(invalid)})

    assert result["success"] is False
    assert result["error"] == "INVALID_PROJECT"


def test_inspect_kdenlive_timeline_does_not_write_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")
    before = set(tmp_path.iterdir())

    result = _mcp_call(
        "inspect_kdenlive_timeline",
        {"project": str(RECON_DIR / "manual_trimmed_clip.kdenlive")},
    )

    assert result["success"] is True
    assert set(tmp_path.iterdir()) == before


def _extract_document(name: str) -> TimelineDocument:
    return KdenliveProjectAdapter().extract_timeline_document(RECON_DIR / name)


def _export_timeline(project_name: str, output_directory, **kwargs):
    return _mcp_call(
        "export_kdenlive_timeline",
        {
            "project": str(RECON_DIR / f"{project_name}.kdenlive"),
            "output_directory": str(output_directory),
            **kwargs,
        },
    )


def _allow_export(monkeypatch, tmp_path, project_dirs=None, output_dirs=None) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS", project_dirs or str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", output_dirs or str(tmp_path))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")


def test_export_kdenlive_timeline_creates_valid_file(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("manual_two_clips_timeline", tmp_path)

    assert result["success"] is True
    assert result["operation"] == "export_kdenlive_timeline"
    assert any(warning.get("code") == "TIMELINE_EXPORTED_FROM_KDENLIVE" for warning in result["warnings"])
    timeline_file = Path(result["timeline_file"])
    assert timeline_file.exists()
    loaded = load_timeline_document(timeline_file)
    assert loaded.fps == 30.0
    assert len(loaded.clips) == 4


def test_export_kdenlive_timeline_preserves_trim(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("manual_trimmed_clip", tmp_path)

    loaded = load_timeline_document(Path(result["timeline_file"]))
    assert any(clip.source_in != 0 for clip in loaded.clips)


def test_export_kdenlive_timeline_preserves_gap_positions(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    gap_result = _export_timeline("manual_gap_timeline", tmp_path, name="gap")
    base_result = _export_timeline("manual_two_clips_timeline", tmp_path, name="base")

    gap_doc = load_timeline_document(Path(gap_result["timeline_file"]))
    base_doc = load_timeline_document(Path(base_result["timeline_file"]))
    gap_second = sorted([c for c in gap_doc.clips if c.media.endswith("sample1.mp4")], key=lambda c: c.timeline_in)[0]
    base_second = sorted([c for c in base_doc.clips if c.media.endswith("sample1.mp4")], key=lambda c: c.timeline_in)[0]
    assert gap_second.timeline_in > base_second.timeline_in


def test_export_kdenlive_timeline_rejects_transition_without_output(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("manual_transition_dissolve", tmp_path)

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_TIMELINE_FEATURE"
    assert not list(tmp_path.glob("*.timeline.json"))


def test_export_kdenlive_timeline_rejects_effect_without_output(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("manual_basic_effect", tmp_path)

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_TIMELINE_FEATURE"
    assert not list(tmp_path.glob("*.timeline.json"))


def test_export_kdenlive_timeline_output_exists(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)
    assert _export_timeline("manual_two_clips_timeline", tmp_path)["success"] is True

    result = _export_timeline("manual_two_clips_timeline", tmp_path)

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"


def test_export_kdenlive_timeline_overwrite_replaces(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)
    first = _export_timeline("manual_two_clips_timeline", tmp_path)
    first_path = Path(first["timeline_file"])
    assert first_path.exists()

    result = _export_timeline("manual_two_clips_timeline", tmp_path, overwrite=True)

    assert result["success"] is True
    assert Path(result["timeline_file"]).exists()


def test_export_kdenlive_timeline_rejects_outside_allowlist(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path, project_dirs=str(tmp_path))
    result = _export_timeline("manual_two_clips_timeline", tmp_path)
    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"

    _allow_export(monkeypatch, tmp_path, output_dirs=str(tmp_path / "nowhere"))
    result = _export_timeline("manual_two_clips_timeline", tmp_path / "other")
    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_export_kdenlive_timeline_via_mcp_response_shape(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("manual_two_clips_timeline", tmp_path)

    assert set(result) >= {"success", "operation", "project", "timeline_file", "timeline", "warnings"}
    assert result["timeline"]["schema_version"] == 1


def test_export_kdenlive_timeline_accepts_null_name(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _mcp_call(
        "export_kdenlive_timeline",
        {
            "project": str(RECON_DIR / "manual_two_clips_timeline.kdenlive"),
            "output_directory": str(tmp_path),
            "name": None,
        },
    )

    assert result["success"] is True
    expected = tmp_path / "manual_two_clips_timeline.timeline.json"
    assert result["timeline_file"] == str(expected)
    assert expected.exists()


_COMPLEX_FIXTURES = [
    "multiple_effect_stack_on_clip.kdenlive",
    "multiple_transitions_timeline.kdenlive",
    "proxy_fixture.kdenlive",
]


@pytest.mark.parametrize("name", _COMPLEX_FIXTURES)
def test_export_kdenlive_timeline_rejects_complex_fixture(monkeypatch, tmp_path, name: str) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _mcp_call(
        "export_kdenlive_timeline",
        {
            "project": str(RECON_DIR / name),
            "output_directory": str(tmp_path),
            "name": name,
        },
    )

    assert result["success"] is False
    assert result["operation"] == "export_kdenlive_timeline"
    assert result["error"] == "UNSUPPORTED_TIMELINE_FEATURE"
    assert isinstance(result["message"], str) and result["message"]
    assert isinstance(result["warnings"], list)
    assert "timeline_file" not in result
    assert not list(tmp_path.glob("*.timeline.json"))


def test_apply_timeline_edits_fade_via_mcp_boundary(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)
    exported = _export_timeline("manual_two_clips_timeline", tmp_path)

    result = _mcp_call(
        "apply_timeline_edits",
        {
            "timeline_file": exported["timeline_file"],
            "edits": [
                {"operation": "fade_in_audio", "clip_id": "chain0_a", "duration_ms": 500},
                {"operation": "fade_out_audio", "clip_id": "chain0_a", "duration_ms": 400},
            ],
            "output_directory": str(tmp_path),
            "name": "fade_via_mcp",
            "dry_run": True,
        },
    )

    assert result["success"] is True
    clips = {clip["id"]: clip for clip in result["timeline"]["clips"]}
    assert clips["chain0_a"]["effects"] == [
        {"id": "chain0_a_fadein", "kind": "fadein", "window_ms": 500, "points": []},
        {"id": "chain0_a_fadeout", "kind": "fadeout", "window_ms": 400, "points": []},
    ]


def test_export_kdenlive_timeline_roundtrip_preserves_fade_effects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    _allow_export(monkeypatch, tmp_path, project_dirs=f"{RECON_DIR}:{tmp_path}")

    exported = _export_timeline("manual_two_clips_timeline", tmp_path, name="fade_rt_base")
    edited = _mcp_call(
        "apply_timeline_edits",
        {
            "timeline_file": exported["timeline_file"],
            "edits": [
                {"operation": "fade_in_audio", "clip_id": "chain0_a", "duration_ms": 500},
                {"operation": "fade_out_audio", "clip_id": "chain0_a", "duration_ms": 400},
            ],
            "output_directory": str(tmp_path),
            "name": "fade_rt_edited",
            "dry_run": False,
        },
    )
    assert edited["success"] is True

    prepared = _mcp_call(
        "prepare_working_project",
        {
            "project": str(RECON_DIR / "manual_two_clips_timeline.kdenlive"),
            "output_directory": str(tmp_path),
            "lock_directory": str(tmp_path / "locks"),
            "owner": "agent",
        },
    )
    applied = _mcp_call(
        "apply_timeline_to_working_project",
        {
            "working_project": prepared["working_project"],
            "timeline_file": edited["timeline_file"],
            "output_directory": str(tmp_path),
            "name": "fade_rt_output",
        },
    )
    assert applied["success"] is True

    readback = _mcp_call(
        "export_kdenlive_timeline",
        {
            "project": applied["output_project"],
            "output_directory": str(tmp_path),
            "name": "fade_rt_readback",
        },
    )
    assert readback["success"] is True
    faded_clips = [clip for clip in readback["timeline"]["clips"] if clip.get("effects")]
    assert len(faded_clips) == 1
    effects = faded_clips[0]["effects"]
    assert {effect["kind"]: effect["window_ms"] for effect in effects} == {"fadein": 500, "fadeout": 400}


def test_extract_timeline_document_converts_audio_fade_fixture_volume_keyframes() -> None:
    document = _extract_document("audio_fade_fixture.kdenlive")
    faded = [clip for clip in document.clips if clip.effects]

    assert len(faded) == 1
    kinds = {effect.kind for effect in faded[0].effects}
    assert kinds == {"fadein", "fadeout", "volume_keyframes"}
    curve = next(effect for effect in faded[0].effects if effect.kind == "volume_keyframes")
    assert [(point.position_s, point.value) for point in curve.points] == [
        (0.0, 0.01),
        (1.233333, 0.5),
        (1.833333, 0.5),
        (2.666667, 0.5),
    ]


def test_export_kdenlive_timeline_accepts_audio_fade_fixture(monkeypatch, tmp_path) -> None:
    _allow_export(monkeypatch, tmp_path)

    result = _export_timeline("audio_fade_fixture", tmp_path)

    assert result["success"] is True
    assert result["timeline_file"] and Path(result["timeline_file"]).exists()


def test_extract_timeline_document_converts_resaved_volume_keyframes() -> None:
    document = _extract_document("audio_volume_keyframes_resaved_by_kdenlive.kdenlive")
    faded = [clip for clip in document.clips if clip.effects]

    assert len(faded) == 1
    curve = next(effect for effect in faded[0].effects if effect.kind == "volume_keyframes")
    assert [(point.position_s, point.value) for point in curve.points] == [
        (0.0, 0.01),
        (1.233333, 0.5),
        (1.833333, 0.5),
        (2.666667, 0.5),
    ]


def test_export_kdenlive_timeline_roundtrip_preserves_volume_curve(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    _allow_export(monkeypatch, tmp_path, project_dirs=f"{RECON_DIR}:{tmp_path}")

    exported = _export_timeline("manual_two_clips_timeline", tmp_path, name="curve_rt_base")
    edited = _mcp_call(
        "apply_timeline_edits",
        {
            "timeline_file": exported["timeline_file"],
            "edits": [
                {
                    "operation": "set_clip_volume_curve",
                    "clip_id": "chain0_a",
                    "points": [
                        {"position_s": 0.0, "value": 0.01},
                        {"position_s": 1.233, "value": 0.5},
                        {"position_s": 2.667, "value": 0.5},
                    ],
                }
            ],
            "output_directory": str(tmp_path),
            "name": "curve_rt_edited",
            "dry_run": False,
        },
    )
    assert edited["success"] is True

    prepared = _mcp_call(
        "prepare_working_project",
        {
            "project": str(RECON_DIR / "manual_two_clips_timeline.kdenlive"),
            "output_directory": str(tmp_path),
            "lock_directory": str(tmp_path / "locks"),
            "owner": "agent",
        },
    )
    applied = _mcp_call(
        "apply_timeline_to_working_project",
        {
            "working_project": prepared["working_project"],
            "timeline_file": edited["timeline_file"],
            "output_directory": str(tmp_path),
            "name": "curve_rt_output",
        },
    )
    assert applied["success"] is True

    readback = _mcp_call(
        "export_kdenlive_timeline",
        {
            "project": applied["output_project"],
            "output_directory": str(tmp_path),
            "name": "curve_rt_readback",
        },
    )
    assert readback["success"] is True
    curved = [clip for clip in readback["timeline"]["clips"] if clip.get("effects")]
    assert len(curved) == 1
    curve = next(effect for effect in curved[0]["effects"] if effect["kind"] == "volume_keyframes")
    assert [(point["position_s"], point["value"]) for point in curve["points"]] == [
        (0.0, 0.01),
        (1.233333, 0.5),
        (2.666667, 0.5),
    ]


def test_extract_timeline_document_rejects_duplicate_fade_kind(monkeypatch) -> None:
    adapter = KdenliveProjectAdapter()
    synthetic = {
        "fps": 30.0,
        "profile": {"width": 1080, "height": 1920, "frame_rate_num": 30, "frame_rate_den": 1},
        "user_transitions": [],
        "clip_effects": [
            {
                "entry_producer": "chain0",
                "filter_id": "filter0",
                "mlt_service": "volume",
                "kdenlive_id": "fadein",
                "track_kind": "audio",
                "supported": True,
            },
            {
                "entry_producer": "chain0",
                "filter_id": "filter1",
                "mlt_service": "volume",
                "kdenlive_id": "fadein",
                "track_kind": "audio",
                "supported": True,
            },
        ],
        "proxy_media_ids": [],
        "resolved_media": {"4": str(RECON_DIR / "sample1.mp4")},
        "tracks": [
            {"id": "playlist0", "track_kind": "audio", "clip_count": 1, "gap_count": 0},
        ],
        "timeline_clips": [
            {
                "producer": "chain0",
                "playlist_id": "playlist0",
                "track_kind": "audio",
                "media": "sample1.mp4",
                "media_id": "4",
                "source_in_frames": 0,
                "source_out_frames": 89,
                "duration_frames": 90,
                "position_frames": 0,
                "supported_audio_fades": [
                    {"kind": "fadein", "window_ms": 500, "gain": "0", "end": "1"},
                    {"kind": "fadein", "window_ms": 700, "gain": "0", "end": "1"},
                ],
            }
        ],
        "confirmed_fields": [],
        "inferred_fields": [],
    }
    monkeypatch.setattr(adapter, "extract_timeline_summary", lambda project: synthetic)

    with pytest.raises(KdenliveProjectError) as excinfo:
        adapter.extract_timeline_document("dummy.kdenlive")
    assert excinfo.value.code == "UNSUPPORTED_TIMELINE_FEATURE"
    assert "duplicate audio fades" in excinfo.value.message


def test_extract_timeline_document_rejects_fade_on_video_track(monkeypatch) -> None:
    adapter = KdenliveProjectAdapter()
    synthetic = {
        "fps": 30.0,
        "profile": {"width": 1080, "height": 1920, "frame_rate_num": 30, "frame_rate_den": 1},
        "user_transitions": [],
        "clip_effects": [
            {
                "entry_producer": "chain0",
                "filter_id": "filter0",
                "mlt_service": "volume",
                "kdenlive_id": "fadein",
                "track_kind": "video",
                "supported": False,
            }
        ],
        "proxy_media_ids": [],
        "resolved_media": {"4": str(RECON_DIR / "sample1.mp4")},
        "tracks": [
            {"id": "playlist6", "track_kind": "video", "clip_count": 1, "gap_count": 0},
        ],
        "timeline_clips": [
            {
                "producer": "chain0",
                "playlist_id": "playlist6",
                "track_kind": "video",
                "media": "sample1.mp4",
                "media_id": "4",
                "source_in_frames": 0,
                "source_out_frames": 89,
                "duration_frames": 90,
                "position_frames": 0,
                "supported_audio_fades": [],
            }
        ],
        "confirmed_fields": [],
        "inferred_fields": [],
    }
    monkeypatch.setattr(adapter, "extract_timeline_summary", lambda project: synthetic)

    with pytest.raises(KdenliveProjectError) as excinfo:
        adapter.extract_timeline_document("dummy.kdenlive")
    assert excinfo.value.code == "UNSUPPORTED_TIMELINE_FEATURE"


def test_classify_audio_fade_criteria() -> None:
    from kdenlive_mcp.adapters.kdenlive_xml import _classify_audio_fade

    base_fadein = {
        "window": "500",
        "max_gain": "20dB",
        "channel_mask": "-1",
        "mlt_service": "volume",
        "kdenlive_id": "fadein",
        "gain": "0",
        "end": "1",
    }
    supported, fade = _classify_audio_fade("audio", base_fadein)
    assert supported is True
    assert fade == {"kind": "fadein", "window_ms": 500, "gain": "0", "end": "1"}

    fadeout = {**base_fadein, "kdenlive_id": "fadeout", "gain": "1", "end": "0"}
    supported, fade = _classify_audio_fade("audio", fadeout)
    assert supported is True
    assert fade["kind"] == "fadeout"
    assert fade["window_ms"] == 500

    keyframed = {**base_fadein, "level": "00:00:00.000=1;00:00:01.000=50"}
    assert _classify_audio_fade("audio", keyframed)[0] is False

    video_track = _classify_audio_fade("video", base_fadein)
    assert video_track[0] is False

    wrong_gain = {**base_fadein, "gain": "1", "end": "0"}
    assert _classify_audio_fade("audio", wrong_gain)[0] is False

    no_window = {k: v for k, v in base_fadein.items() if k != "window"}
    assert _classify_audio_fade("audio", no_window)[0] is False

    bad_window = {**base_fadein, "window": "abc"}
    assert _classify_audio_fade("audio", bad_window)[0] is False

    zero_window = {**base_fadein, "window": "0"}
    assert _classify_audio_fade("audio", zero_window)[0] is False

    other_service = {**base_fadein, "mlt_service": "qtblend"}
    assert _classify_audio_fade("audio", other_service)[0] is False


def test_classify_volume_keyframes_rejects_non_finite_values() -> None:
    from kdenlive_mcp.adapters.kdenlive_xml import _classify_volume_keyframes

    base = {"mlt_service": "volume", "kdenlive_id": "volume"}

    nan = {**base, "level": "00:00:00.000=1;00:00:01.000=nan"}
    assert _classify_volume_keyframes("audio", nan, 30, 1, 3.0) is None

    pos_inf = {**base, "level": "00:00:00.000=1;00:00:01.000=inf"}
    assert _classify_volume_keyframes("audio", pos_inf, 30, 1, 3.0) is None

    neg_inf = {**base, "level": "00:00:00.000=1;00:00:01.000=-inf"}
    assert _classify_volume_keyframes("audio", neg_inf, 30, 1, 3.0) is None


def test_classify_volume_keyframes_rejects_non_integer_resolution() -> None:
    from kdenlive_mcp.adapters.kdenlive_xml import _classify_volume_keyframes

    base = {"mlt_service": "volume", "kdenlive_id": "volume"}
    decimal_level = {**base, "level": "00:00:00.000=1;00:00:01.000=33.5"}
    assert _classify_volume_keyframes("audio", decimal_level, 30, 1, 3.0) is None


def test_extract_timeline_document_rejects_unsupported_volume_level(monkeypatch) -> None:
    adapter = KdenliveProjectAdapter()
    synthetic = {
        "fps": 30.0,
        "profile": {"width": 1080, "height": 1920, "frame_rate_num": 30, "frame_rate_den": 1},
        "user_transitions": [],
        "clip_effects": [
            {
                "entry_producer": "chain0",
                "filter_id": "filter0",
                "mlt_service": "volume",
                "kdenlive_id": "volume",
                "track_kind": "audio",
                "supported": False,
            }
        ],
        "proxy_media_ids": [],
        "resolved_media": {"4": str(RECON_DIR / "sample1.mp4")},
        "tracks": [
            {"id": "playlist0", "track_kind": "audio", "clip_count": 1, "gap_count": 0},
        ],
        "timeline_clips": [
            {
                "producer": "chain0",
                "playlist_id": "playlist0",
                "track_kind": "audio",
                "media": "sample1.mp4",
                "media_id": "4",
                "source_in_frames": 0,
                "source_out_frames": 89,
                "duration_frames": 90,
                "position_frames": 0,
                "supported_audio_fades": [],
                "supported_volume_keyframes": [],
            }
        ],
        "confirmed_fields": [],
        "inferred_fields": [],
    }
    monkeypatch.setattr(adapter, "extract_timeline_summary", lambda project: synthetic)

    with pytest.raises(KdenliveProjectError) as excinfo:
        adapter.extract_timeline_document("dummy.kdenlive")
    assert excinfo.value.code == "UNSUPPORTED_TIMELINE_FEATURE"


def test_extract_timeline_document_two_clips_validates() -> None:
    document = _extract_document("manual_two_clips_timeline.kdenlive")
    validated = TimelineDocument.model_validate(document.model_dump(mode="json", exclude_none=True))

    assert validated.fps == 30.0
    assert len(validated.tracks) == 2
    assert len(validated.clips) == 4


def test_extract_timeline_document_preserves_trim() -> None:
    document = _extract_document("manual_trimmed_clip.kdenlive")

    assert any(clip.source_in != 0 for clip in document.clips)
    TimelineDocument.model_validate(document.model_dump(mode="json", exclude_none=True))


def test_extract_timeline_document_preserves_gap_positions() -> None:
    gap_document = _extract_document("manual_gap_timeline.kdenlive")
    base_document = _extract_document("manual_two_clips_timeline.kdenlive")

    gap_second = sorted([c for c in gap_document.clips if c.media.endswith("sample1.mp4")], key=lambda c: c.timeline_in)[0]
    base_second = sorted([c for c in base_document.clips if c.media.endswith("sample1.mp4")], key=lambda c: c.timeline_in)[0]
    assert gap_second.timeline_in > base_second.timeline_in
    TimelineDocument.model_validate(gap_document.model_dump(mode="json", exclude_none=True))


def test_extract_timeline_document_rejects_user_transitions() -> None:
    with pytest.raises(KdenliveProjectError) as excinfo:
        _extract_document("manual_transition_dissolve.kdenlive")
    assert excinfo.value.code == "UNSUPPORTED_TIMELINE_FEATURE"


def test_extract_timeline_document_rejects_clip_effects() -> None:
    with pytest.raises(KdenliveProjectError) as excinfo:
        _extract_document("manual_basic_effect.kdenlive")
    assert excinfo.value.code == "UNSUPPORTED_TIMELINE_FEATURE"


def test_extract_timeline_document_does_not_write_files(tmp_path) -> None:
    before = set(tmp_path.iterdir())
    _extract_document("manual_two_clips_timeline.kdenlive")
    assert set(tmp_path.iterdir()) == before


def test_extract_timeline_document_creates_track_per_playlist(monkeypatch) -> None:
    adapter = KdenliveProjectAdapter()
    synthetic = {
        "fps": 30.0,
        "profile": {"width": 1080, "height": 1920, "frame_rate_num": 30, "frame_rate_den": 1},
        "user_transitions": [],
        "clip_effects": [],
        "tracks": [
            {"id": "playlist6", "track_kind": "video", "clip_count": 1, "gap_count": 0},
            {"id": "playlist8", "track_kind": "video", "clip_count": 1, "gap_count": 0},
        ],
        "timeline_clips": [
            {
                "producer": "chain2",
                "playlist_id": "playlist6",
                "track_kind": "video",
                "media": "/media/a.mp4",
                "media_id": "4",
                "source_in_frames": 0,
                "source_out_frames": 89,
                "duration_frames": 90,
                "position_frames": 0,
            },
            {
                "producer": "chain9",
                "playlist_id": "playlist8",
                "track_kind": "video",
                "media": "/media/b.mp4",
                "media_id": "5",
                "source_in_frames": 0,
                "source_out_frames": 59,
                "duration_frames": 60,
                "position_frames": 0,
            },
        ],
        "confirmed_fields": [],
        "inferred_fields": [],
    }
    monkeypatch.setattr(adapter, "extract_timeline_summary", lambda project: synthetic)

    document = adapter.extract_timeline_document("dummy.kdenlive")

    video_tracks = [track for track in document.tracks if track.type == "video"]
    assert len(video_tracks) == 2
    clips_by_id = {clip.id: clip for clip in document.clips}
    assert clips_by_id["chain2_v"].track_id == video_tracks[0].id
    assert clips_by_id["chain9_v"].track_id == video_tracks[1].id
    assert clips_by_id["chain2_v"].track_id != clips_by_id["chain9_v"].track_id
    assert video_tracks[0].id.endswith("playlist6")
    assert video_tracks[1].id.endswith("playlist8")


def test_extract_timeline_document_track_names_are_simple() -> None:
    document = _extract_document("manual_two_clips_timeline.kdenlive")

    names = {track.name for track in document.tracks}
    assert names == {"Video 1", "Audio 1"}


def test_extract_timeline_document_loses_no_convertible_clip() -> None:
    adapter = KdenliveProjectAdapter()
    summary = adapter.extract_timeline_summary(RECON_DIR / "manual_two_clips_timeline.kdenlive")
    document = adapter.extract_timeline_document(RECON_DIR / "manual_two_clips_timeline.kdenlive")

    convertible = [clip for clip in summary["timeline_clips"] if clip.get("media") and int(clip.get("duration_frames") or 0) > 0]
    assert len(document.clips) == len(convertible)


def test_extract_timeline_document_links_audio_video_pairs() -> None:
    document = _extract_document("manual_two_clips_timeline.kdenlive")
    by_id = {clip.id: clip for clip in document.clips}

    assert by_id["chain0_a"].linked_clip_id == "chain2_v"
    assert by_id["chain2_v"].linked_clip_id == "chain0_a"
    assert by_id["chain1_a"].linked_clip_id == "chain3_v"
    assert by_id["chain3_v"].linked_clip_id == "chain1_a"
    TimelineDocument.model_validate(document.model_dump(mode="json", exclude_none=True))


def test_extract_timeline_document_trim_keeps_links() -> None:
    document = _extract_document("manual_trimmed_clip.kdenlive")
    by_id = {clip.id: clip for clip in document.clips}

    assert by_id["chain0_a"].linked_clip_id == "chain2_v"
    assert by_id["chain2_v"].linked_clip_id == "chain0_a"
    assert by_id["chain0_a_1"].linked_clip_id == "chain2_v_1"
    assert by_id["chain2_v_1"].linked_clip_id == "chain0_a_1"
    assert by_id["chain1_a"].linked_clip_id == "chain3_v"
    assert by_id["chain3_v"].linked_clip_id == "chain1_a"
    TimelineDocument.model_validate(document.model_dump(mode="json", exclude_none=True))
