from __future__ import annotations

from typing import Any

from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path, ensure_project_path
from kdenlive_mcp.services.timeline_service import (
    create_timeline_from_rough_cut_plan,
    export_timeline_to_kdenlive_template,
    save_timeline,
)
from kdenlive_mcp.tools.rough_cut_tools import create_rough_cut_plan_file


def _failed_step(step: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": False,
        "operation": "create_vlog_rough_cut_project",
        "failed_step": step,
        "error": result.get("error", "WORKFLOW_STEP_FAILED"),
        "message": result.get("message", f"Workflow step failed: {step}"),
        "step_result": result,
    }


def _preflight(folder: str, template_project: str, output_directory: str) -> dict[str, Any] | None:
    try:
        ensure_media_path(folder)
        ensure_output_path(output_directory)
        template = ensure_project_path(template_project)
        ensure_project_path(output_directory)
    except SecurityError as exc:
        return {
            "success": False,
            "error": exc.code,
            "message": exc.message,
        }
    if not template.exists():
        return {
            "success": False,
            "error": "PROJECT_NOT_FOUND",
            "message": f"Template project does not exist: {template}",
        }
    return None


def create_vlog_rough_cut_project(
    folder: str,
    template_project: str,
    output_directory: str,
    name: str = "vlog_ai_001",
    target_duration: float = 60.0,
    recursive: bool = True,
    max_files: int = 25,
    remove_silence: bool = True,
    silence_threshold_db: float = -35.0,
    silence_minimum_duration: float = 0.8,
    padding_before: float = 0.15,
    padding_after: float = 0.15,
    min_segment_duration: float = 0.25,
    fps: float = 30.0,
    width: int = 1080,
    height: int = 1920,
    overwrite: bool = False,
) -> dict[str, Any]:
    preflight_error = _preflight(folder, template_project, output_directory)
    if preflight_error is not None:
        return _failed_step("preflight", preflight_error)

    plan_result = create_rough_cut_plan_file(
        folder=folder,
        output_directory=output_directory,
        name=f"{name}_rough_cut_plan",
        overwrite=overwrite,
        target_duration=target_duration,
        recursive=recursive,
        max_files=max_files,
        remove_silence=remove_silence,
        silence_threshold_db=silence_threshold_db,
        silence_minimum_duration=silence_minimum_duration,
        padding_before=padding_before,
        padding_after=padding_after,
        min_segment_duration=min_segment_duration,
    )
    if not plan_result.get("success"):
        return _failed_step("create_rough_cut_plan_file", plan_result)

    timeline_result = create_timeline_from_rough_cut_plan(
        plan_file=plan_result["plan_file"],
        fps=fps,
        width=width,
        height=height,
    )
    if not timeline_result.get("success"):
        return _failed_step("create_timeline_from_rough_cut_plan", timeline_result)

    saved_timeline = save_timeline(
        timeline=timeline_result["timeline"],
        output_directory=output_directory,
        name=f"{name}_timeline",
        overwrite=overwrite,
    )
    if not saved_timeline.get("success"):
        return _failed_step("save_timeline", saved_timeline)

    project_result = export_timeline_to_kdenlive_template(
        timeline_file=saved_timeline["timeline_file"],
        template_project=template_project,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        check_media_exists=True,
    )
    if not project_result.get("success"):
        return _failed_step("export_timeline_to_kdenlive_template", project_result)

    return {
        "success": True,
        "operation": "create_vlog_rough_cut_project",
        "folder": folder,
        "template_project": template_project,
        "output_directory": output_directory,
        "project": project_result["project"],
        "artifacts": {
            "rough_cut_plan": plan_result["plan_file"],
            "timeline": saved_timeline["timeline_file"],
            "kdenlive_project": project_result["project"],
        },
        "steps": {
            "rough_cut_plan": {
                "success": True,
                "planned_duration": plan_result["plan"]["planned_duration"],
                "selected_segment_count": plan_result["plan"]["selected_segment_count"],
            },
            "timeline": {
                "success": True,
                **timeline_result["summary"],
            },
            "kdenlive_project": {
                "success": True,
                **project_result["inspection_summary"],
            },
        },
    }
