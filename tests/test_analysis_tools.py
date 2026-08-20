from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from kdenlive_mcp.tools import analysis_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SAMPLE_VIDEO = RECON_DIR / "sample1.mp4"


def _allow(monkeypatch, output_dir: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(output_dir))


def _make_black_color_black_video(path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for blackdetect integration test")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:size=160x90:rate=30:duration=1",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=30:duration=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:size=160x90:rate=30:duration=1",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[out]",
        "-map",
        "[out]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    completed = subprocess.run(command, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        pytest.fail(completed.stderr.decode("utf-8", errors="replace"))


def _make_scene_change_video(path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for scene detection integration test")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:size=160x90:rate=30:duration=1",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=30:duration=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:size=160x90:rate=30:duration=1",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[out]",
        "-map",
        "[out]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    completed = subprocess.run(command, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        pytest.fail(completed.stderr.decode("utf-8", errors="replace"))


def _make_freeze_video(path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for freezedetect integration test")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:size=160x90:rate=30:duration=2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    completed = subprocess.run(command, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        pytest.fail(completed.stderr.decode("utf-8", errors="replace"))


def test_extract_frames(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output_dir = tmp_path / "frames"

    result = analysis_tools.extract_frames(
        media=str(SAMPLE_VIDEO),
        output_directory=str(output_dir),
        every_seconds=1.0,
        max_frames=3,
        prefix="sample",
    )

    assert result["success"] is True
    assert result["frame_count"] == 3
    assert [Path(path).name for path in result["frames"]] == [
        "sample_0001.jpg",
        "sample_0002.jpg",
        "sample_0003.jpg",
    ]
    assert all(Path(path).stat().st_size > 0 for path in result["frames"])


def test_extract_frames_refuses_existing_prefix(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output_dir = tmp_path / "frames"
    output_dir.mkdir()
    existing = output_dir / "sample_0001.jpg"
    existing.write_bytes(b"existing")

    result = analysis_tools.extract_frames(
        media=str(SAMPLE_VIDEO),
        output_directory=str(output_dir),
        prefix="sample",
    )

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert existing.read_bytes() == b"existing"


def test_generate_contact_sheet(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output = tmp_path / "contact.jpg"

    result = analysis_tools.generate_contact_sheet(
        media=str(SAMPLE_VIDEO),
        output=str(output),
        every_seconds=1.0,
        columns=2,
        rows=2,
        thumb_width=160,
    )

    assert result["success"] is True
    assert output.exists()
    assert output.stat().st_size > 0


def test_generate_contact_sheet_refuses_existing_output(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    output = tmp_path / "contact.jpg"
    output.write_bytes(b"existing")

    result = analysis_tools.generate_contact_sheet(
        media=str(SAMPLE_VIDEO),
        output=str(output),
    )

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"existing"


def test_parse_blackdetect_output() -> None:
    output = (
        "[blackdetect @ 0x123] black_start:0 black_end:1.0 black_duration:1.0\n"
        "[blackdetect @ 0x123] black_start:2 black_end:3 black_duration:1\n"
    )

    assert analysis_tools._parse_blackdetect_output(output) == [
        {"start": 0.0, "end": 1.0, "duration": 1.0},
        {"start": 2.0, "end": 3.0, "duration": 1.0},
    ]


def test_detect_black_frames_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "black_color_black.mp4"
    _make_black_color_black_video(media)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_black_frames(
        media=str(media),
        minimum_duration=0.5,
        picture_black_ratio=0.98,
        pixel_black_threshold=0.1,
    )

    assert result["success"] is True
    assert result["black_interval_count"] >= 2
    first = result["black_intervals"][0]
    assert first["start"] == pytest.approx(0.0, abs=0.05)
    assert first["duration"] == pytest.approx(1.0, abs=0.1)


def test_detect_black_frames_rejects_invalid_ratio(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "placeholder.mp4"
    media.write_bytes(b"not a real video")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_black_frames(str(media), picture_black_ratio=1.5)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"


def test_parse_scene_change_output() -> None:
    output = """
    [Parsed_showinfo_1 @ 0x123] n:   0 pts:     30 pts_time:1
    [Parsed_showinfo_1 @ 0x123] n:   1 pts:     60 pts_time:2.000000
    """

    assert analysis_tools._parse_scene_change_output(output) == [
        {"time": 1.0},
        {"time": 2.0},
    ]


def test_detect_scene_changes_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "scene_changes.mp4"
    _make_scene_change_video(media)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_scene_changes(
        media=str(media),
        threshold=0.2,
    )

    assert result["success"] is True
    assert result["scene_change_count"] >= 1
    times = [item["time"] for item in result["scene_changes"]]
    assert any(time == pytest.approx(1.0, abs=0.15) for time in times)


def test_detect_scene_changes_rejects_invalid_threshold(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "placeholder.mp4"
    media.write_bytes(b"not a real video")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_scene_changes(str(media), threshold=1.2)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"


def test_parse_freezedetect_output() -> None:
    output = """
    [freezedetect @ 0x123] freeze_start: 0
    [freezedetect @ 0x123] freeze_duration: 1.5
    [freezedetect @ 0x123] freeze_end: 1.5
    """

    assert analysis_tools._parse_freezedetect_output(output) == [
        {"start": 0.0, "end": 1.5, "duration": 1.5}
    ]


def test_parse_freezedetect_output_closes_freeze_at_eof() -> None:
    output = "[freezedetect @ 0x123] lavfi.freezedetect.freeze_start: 0\n"

    assert analysis_tools._parse_freezedetect_output(output, media_duration=2.0) == [
        {"start": 0.0, "end": 2.0, "duration": 2.0}
    ]


def test_detect_freeze_frames_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "freeze.mp4"
    _make_freeze_video(media)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_freeze_frames(
        media=str(media),
        noise_db=-60,
        minimum_duration=0.5,
    )

    assert result["success"] is True
    assert result["freeze_interval_count"] >= 1
    first = result["freeze_intervals"][0]
    assert first["start"] == pytest.approx(0.0, abs=0.1)
    assert first["duration"] >= 1.0


def test_detect_freeze_frames_rejects_invalid_noise(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "placeholder.mp4"
    media.write_bytes(b"not a real video")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = analysis_tools.detect_freeze_frames(str(media), noise_db=0)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"
