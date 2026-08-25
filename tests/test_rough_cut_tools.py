from __future__ import annotations

from pathlib import Path

import pytest

from kdenlive_mcp.tools import rough_cut_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"


def test_keep_segments_from_cuts_returns_complement_ranges() -> None:
    segments = rough_cut_tools._keep_segments_from_cuts(
        duration=6.0,
        cuts=[
            {"start": 1.0, "end": 2.0},
            {"start": 4.0, "end": 5.0},
        ],
    )

    assert segments == [
        {"start": 0.0, "end": 1.0},
        {"start": 2.0, "end": 4.0},
        {"start": 5.0, "end": 6.0},
    ]


def test_plan_rough_cut_reaches_target_with_trimmed_last_segment(monkeypatch) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))

    result = rough_cut_tools.plan_rough_cut(
        folder=str(RECON_DIR),
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    assert result["success"] is True
    assert result["operation"] == "plan_rough_cut"
    assert result["dry_run"] is True
    assert result["planned_duration"] == pytest.approx(4.0)
    assert result["selected_segment_count"] == 2
    assert result["segments"][0]["timeline_in"] == pytest.approx(0.0)
    assert result["segments"][0]["timeline_out"] == pytest.approx(3.0)
    assert result["segments"][1]["duration"] == pytest.approx(1.0)
    assert result["segments"][1]["source_out"] == pytest.approx(1.0)


def test_plan_rough_cut_rejects_invalid_target_duration() -> None:
    result = rough_cut_tools.plan_rough_cut(folder=str(RECON_DIR), target_duration=0)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"


def test_plan_rough_cut_rejects_excessive_file_limit() -> None:
    result = rough_cut_tools.plan_rough_cut(folder=str(RECON_DIR), max_files=501)

    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENT"
