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
