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


def test_save_and_inspect_rough_cut_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    plan = rough_cut_tools.plan_rough_cut(
        folder=str(RECON_DIR),
        target_duration=4.0,
        recursive=False,
        max_files=2,
        remove_silence=False,
    )

    saved = rough_cut_tools.save_rough_cut_plan(
        plan=plan,
        output_directory=str(tmp_path),
        name="Vlog Rough Cut",
    )

    assert saved["success"] is True
    plan_file = Path(saved["plan_file"])
    assert plan_file.exists()
    assert plan_file.name == "Vlog_Rough_Cut.rough-cut-plan.json"
    assert saved["data"]["kind"] == "kdenlive_mcp_rough_cut_plan"
    assert saved["data"]["schema_version"] == 1

    inspected = rough_cut_tools.inspect_rough_cut_plan(str(plan_file))
    assert inspected["success"] is True
    assert inspected["data"]["plan"]["selected_segment_count"] == 2


def test_create_rough_cut_plan_file(monkeypatch, tmp_path: Path) -> None:
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
    assert result["operation"] == "create_rough_cut_plan_file"
    assert Path(result["plan_file"]).exists()
    assert result["plan"]["planned_duration"] == pytest.approx(4.0)


def test_save_rough_cut_plan_refuses_existing_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path))
    plan = rough_cut_tools.plan_rough_cut(
        folder=str(RECON_DIR),
        recursive=False,
        max_files=1,
        remove_silence=False,
    )

    first = rough_cut_tools.save_rough_cut_plan(plan=plan, output_directory=str(tmp_path), name="existing")
    second = rough_cut_tools.save_rough_cut_plan(plan=plan, output_directory=str(tmp_path), name="existing")

    assert first["success"] is True
    assert second["success"] is False
    assert second["error"] == "OUTPUT_EXISTS"


def test_save_rough_cut_plan_requires_output_allowlist(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path / "allowed"))
    plan = {
        "success": True,
        "operation": "plan_rough_cut",
        "dry_run": True,
        "segments": [],
    }

    result = rough_cut_tools.save_rough_cut_plan(
        plan=plan,
        output_directory=str(tmp_path / "denied"),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_save_rough_cut_plan_rejects_failed_plan(tmp_path: Path) -> None:
    result = rough_cut_tools.save_rough_cut_plan(
        plan={"success": False, "operation": "plan_rough_cut", "dry_run": True, "segments": []},
        output_directory=str(tmp_path),
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_ROUGH_CUT_PLAN"
