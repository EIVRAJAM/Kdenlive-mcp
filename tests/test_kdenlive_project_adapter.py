from pathlib import Path

from kdenlive_mcp.adapters.commands import CommandResult
from kdenlive_mcp.adapters.kdenlive_xml import (
    KdenliveProjectAdapter,
    frame_to_kdenlive_timecode,
    parse_timecode_to_frames,
    seconds_to_kdenlive_in_timecode,
    seconds_to_kdenlive_out_timecode,
)
from kdenlive_mcp.tools import project_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
TWO_CLIPS_PROJECT = RECON_DIR / "manual_two_clips_timeline.kdenlive"
MARKER_PROJECT = RECON_DIR / "manual_trim_marker.kdenlive"


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
