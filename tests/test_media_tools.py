from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.tools import media_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SAMPLE_VIDEO = RECON_DIR / "sample1.mp4"


def _allow_recon(monkeypatch, output_dir: Path | None = None) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(output_dir or RECON_DIR))


def test_list_media_without_probe(monkeypatch) -> None:
    _allow_recon(monkeypatch)

    result = media_tools.list_media(str(RECON_DIR))

    assert result["success"] is True
    assert result["count"] >= 2
    assert str(SAMPLE_VIDEO) in {item["path"] for item in result["media"]}


def test_get_media_info_uses_ffprobe(monkeypatch) -> None:
    _allow_recon(monkeypatch)

    result = media_tools.get_media_info(str(SAMPLE_VIDEO))

    assert result["success"] is True
    assert result["media"]["video"]["codec"] == "h264"
    assert result["media"]["audio"]["codec"] == "aac"
    assert result["media"]["duration_seconds"] == 3.0


def test_validate_media(monkeypatch) -> None:
    _allow_recon(monkeypatch)

    result = media_tools.validate_media(str(SAMPLE_VIDEO))

    assert result["success"] is True
    assert result["valid"] is True
    assert result["has_video"] is True
    assert result["has_audio"] is True


def test_path_traversal_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))

    result = media_tools.get_media_info(str(tmp_path / ".." / "outside.mp4"))

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_generate_thumbnail(monkeypatch, tmp_path: Path) -> None:
    _allow_recon(monkeypatch, output_dir=tmp_path)
    output = tmp_path / "thumb.jpg"

    result = media_tools.generate_thumbnail(str(SAMPLE_VIDEO), str(output), timestamp=1.0)

    assert result["success"] is True
    assert output.exists()
    assert output.stat().st_size > 0


def test_generate_thumbnail_refuses_existing_output(monkeypatch, tmp_path: Path) -> None:
    _allow_recon(monkeypatch, output_dir=tmp_path)
    output = tmp_path / "thumb.jpg"
    output.write_bytes(b"existing")

    result = media_tools.generate_thumbnail(str(SAMPLE_VIDEO), str(output), timestamp=1.0)

    assert result["success"] is False
    assert result["error"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"existing"


def test_extract_audio(monkeypatch, tmp_path: Path) -> None:
    _allow_recon(monkeypatch, output_dir=tmp_path)
    output = tmp_path / "audio.wav"

    result = media_tools.extract_audio(str(SAMPLE_VIDEO), str(output))

    assert result["success"] is True
    assert output.exists()
    assert output.stat().st_size > 0


def test_extract_audio_refuses_original_media_as_output(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(RECON_DIR))

    result = media_tools.extract_audio(str(SAMPLE_VIDEO), str(SAMPLE_VIDEO))

    assert result["success"] is False
    assert result["error"] == "ORIGINAL_MEDIA_PROTECTED"


def _make_media(tmp_path: Path, name: str = "clip.mp4") -> Path:
    path = tmp_path / name
    path.write_bytes(b"dummy")
    return path


def _setup_tmp_media(monkeypatch, tmp_path: Path, name: str = "clip.mp4") -> Path:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(tmp_path))
    return _make_media(tmp_path, name)


def _mock_probe(monkeypatch, payload: dict[str, object]) -> None:
    monkeypatch.setattr(media_tools, "ffprobe_json", lambda path: (None, payload))


def _video_stream(**overrides: object) -> dict[str, object]:
    stream: dict[str, object] = {
        "codec_type": "video",
        "codec_name": "h264",
        "width": "640",
        "height": "360",
        "avg_frame_rate": "30/1",
        "r_frame_rate": "30/1",
        "pix_fmt": "yuv420p",
    }
    stream.update(overrides)
    return stream


def _audio_stream(**overrides: object) -> dict[str, object]:
    stream: dict[str, object] = {
        "codec_type": "audio",
        "codec_name": "aac",
        "sample_rate": "48000",
        "channels": "2",
        "channel_layout": "stereo",
    }
    stream.update(overrides)
    return stream


def test_media_summary_reports_avg_frame_rate_for_vfr(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(
        monkeypatch,
        {
            "streams": [_video_stream(avg_frame_rate="30000/1001", r_frame_rate="30/1")],
            "format": {"duration": "10.0", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        },
    )

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["video"]["fps"] == "30000/1001"


def test_media_summary_treats_invalid_avg_frame_rate_as_none(monkeypatch, tmp_path: Path) -> None:
    for bad_value in ("0/0", "N/A", ""):
        path = _setup_tmp_media(monkeypatch, tmp_path)
        _mock_probe(
            monkeypatch,
            {"streams": [_video_stream(avg_frame_rate=bad_value)], "format": {"duration": "10.0"}},
        )

        result = media_tools.get_media_info(str(path))

        assert result["success"] is True
        assert result["media"]["video"]["fps"] is None


def test_media_summary_reads_rotation_from_tags(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(
        monkeypatch,
        {"streams": [_video_stream(tags={"rotate": "90"})], "format": {}},
    )

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["video"]["rotation"] == "90"


def test_media_summary_reads_rotation_from_side_data(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(
        monkeypatch,
        {
            "streams": [_video_stream(side_data_list=[{"side_data_type": "Display Matrix", "rotation": "-90"}])],
            "format": {},
        },
    )

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["video"]["rotation"] == "-90"


def test_media_summary_audio_only(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(monkeypatch, {"streams": [_audio_stream()], "format": {"duration": "5.0"}})

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["video"] is None
    assert result["media"]["audio"]["codec"] == "aac"
    assert result["media"]["audio"]["sample_rate"] == "48000"


def test_media_summary_video_only(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(monkeypatch, {"streams": [_video_stream()], "format": {"duration": "5.0"}})

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["audio"] is None
    assert result["media"]["video"]["codec"] == "h264"


def test_media_summary_selects_first_video_and_first_audio(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    streams = [
        _audio_stream(codec_name="opus", channels="1"),
        _video_stream(codec_name="hevc"),
        _audio_stream(codec_name="aac", channels="2"),
        _video_stream(codec_name="h264"),
    ]
    _mock_probe(monkeypatch, {"streams": streams, "format": {}})

    result = media_tools.get_media_info(str(path))

    assert result["media"]["video"]["codec"] == "hevc"
    assert result["media"]["audio"]["codec"] == "opus"


def test_media_summary_missing_bitrate_is_none(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(monkeypatch, {"streams": [_video_stream()], "format": {"duration": "5.0"}})

    result = media_tools.get_media_info(str(path))

    assert result["success"] is True
    assert result["media"]["bitrate"] is None


def test_validate_media_accepts_audio_only(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(monkeypatch, {"streams": [_audio_stream()], "format": {}})

    result = media_tools.validate_media(str(path))

    assert result["success"] is True
    assert result["valid"] is True
    assert result["has_audio"] is True
    assert result["has_video"] is False


def test_validate_media_accepts_video_only(monkeypatch, tmp_path: Path) -> None:
    path = _setup_tmp_media(monkeypatch, tmp_path)
    _mock_probe(monkeypatch, {"streams": [_video_stream()], "format": {}})

    result = media_tools.validate_media(str(path))

    assert result["success"] is True
    assert result["valid"] is True
    assert result["has_audio"] is False
    assert result["has_video"] is True
