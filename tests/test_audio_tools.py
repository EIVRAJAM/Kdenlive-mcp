from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from kdenlive_mcp.tools import audio_tools


def _make_audio_with_silence(path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for silence detection integration test")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=48000:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=1",
        "-filter_complex",
        "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map",
        "[out]",
        str(path),
    ]
    completed = subprocess.run(command, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        pytest.fail(completed.stderr.decode("utf-8", errors="replace"))


def test_parse_silencedetect_output() -> None:
    output = """
    [silencedetect @ 0x123] silence_start: 1
    [silencedetect @ 0x123] silence_end: 2.005 | silence_duration: 1.005
    """

    assert audio_tools._parse_silencedetect_output(output) == [
        {"start": 1.0, "end": 2.005, "duration": 1.005}
    ]


def test_detect_silence_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "tone_silence_tone.wav"
    _make_audio_with_silence(media)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = audio_tools.detect_silence(
        media=str(media),
        threshold_db=-35,
        minimum_duration=0.5,
    )

    assert result["success"] is True
    assert result["silence_count"] == 1
    silence = result["silences"][0]
    assert silence["start"] == pytest.approx(1.0, abs=0.05)
    assert silence["end"] == pytest.approx(2.0, abs=0.05)
    assert silence["duration"] == pytest.approx(1.0, abs=0.05)


def test_detect_silence_rejects_invalid_threshold(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "empty.wav"
    media.write_bytes(b"not real audio")
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = audio_tools.detect_silence(str(media), threshold_db=0)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"


def test_build_silence_cut_plan_applies_padding() -> None:
    cuts = audio_tools._build_silence_cut_plan(
        silences=[{"start": 1.0, "end": 2.0, "duration": 1.0}],
        media_duration=3.0,
        padding_before=0.1,
        padding_after=0.2,
    )

    assert cuts == [
        {
            "cut_id": "silence_cut_001",
            "source_silence_start": 1.0,
            "source_silence_end": 2.0,
            "start": 1.1,
            "end": 1.8,
            "duration": 0.7,
        }
    ]


def test_plan_silence_removal_with_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    media = tmp_path / "tone_silence_tone.wav"
    _make_audio_with_silence(media)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = audio_tools.plan_silence_removal(
        media=str(media),
        threshold_db=-35,
        minimum_duration=0.5,
        padding_before=0.1,
        padding_after=0.1,
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["silence_count"] == 1
    assert result["cut_count"] == 1
    assert result["original_duration"] == pytest.approx(3.0, abs=0.05)
    assert result["removed_duration"] == pytest.approx(0.8, abs=0.08)
    assert result["resulting_duration"] == pytest.approx(2.2, abs=0.1)
    assert result["cuts"][0]["start"] == pytest.approx(1.1, abs=0.05)
    assert result["cuts"][0]["end"] == pytest.approx(1.9, abs=0.05)


def test_plan_silence_removal_rejects_negative_padding(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = audio_tools.plan_silence_removal("missing.wav", padding_before=-0.1)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"
