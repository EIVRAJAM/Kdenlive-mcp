from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.tools import analysis_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SAMPLE_VIDEO = RECON_DIR / "sample1.mp4"


def _allow(monkeypatch, output_dir: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(output_dir))


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
