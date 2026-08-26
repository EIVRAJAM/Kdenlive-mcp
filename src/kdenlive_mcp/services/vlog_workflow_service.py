from __future__ import annotations

from typing import Any

from kdenlive_mcp.adapters.commands import run_command
from kdenlive_mcp.config import get_settings
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path, ensure_project_path
from kdenlive_mcp.services.timeline_service import (
    create_timeline_from_rough_cut_plan,
    export_timeline_to_kdenlive_template,
    save_timeline,
)
from kdenlive_mcp.tools.rough_cut_tools import create_rough_cut_plan_file


def _failed_step(
    step: str,
    result: dict[str, Any],
    partial_outputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "operation": "create_vlog_rough_cut_project",
        "failed_step": step,
        "error": result.get("error", "WORKFLOW_STEP_FAILED"),
        "message": result.get("message", f"Workflow step failed: {step}"),
        "step_result": result,
        "partial_outputs": partial_outputs or {},
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


def _flatpak_sandbox_error(text: str) -> bool:
    return "Unable to allocate instance id" in text


def _validate_mlt_load(project: str, timeout: float) -> dict[str, Any]:
    settings = get_settings()
    result = run_command(
        [
            "flatpak",
            "run",
            "--command=melt",
            settings.kdenlive_flatpak_id,
            project,
            "-consumer",
            "null",
            "terminate_on_pause=1",
        ],
        timeout=timeout,
    )
    combined_output = f"{result.stdout}\n{result.stderr}\n{result.error or ''}"
    if result.available and result.returncode == 0:
        return {
            "success": True,
            "checked": True,
            "valid": True,
            "status": "loaded",
            "command": result.command,
            "returncode": result.returncode,
        }
    if _flatpak_sandbox_error(combined_output):
        return {
            "success": True,
            "checked": True,
            "valid": None,
            "status": "unavailable",
            "warning": "FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX",
            "command": result.command,
            "returncode": result.returncode,
        }
    return {
        "success": False,
        "checked": True,
        "valid": False,
        "error": "MLT_ERROR",
        "message": "Generated Kdenlive project failed MLT load validation.",
        "command": result.command,
        "returncode": result.returncode,
        "stderr": result.stderr,
        "command_error": result.error,
    }


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
    check_mlt: bool = False,
    mlt_timeout: float = 20.0,
) -> dict[str, Any]:
    preflight_error = _preflight(folder, template_project, output_directory)
    if preflight_error is not None:
        return _failed_step("preflight", preflight_error)

    partial_outputs: dict[str, str] = {}
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
        return _failed_step("create_rough_cut_plan_file", plan_result, partial_outputs)
    partial_outputs["rough_cut_plan"] = plan_result["plan_file"]

    timeline_result = create_timeline_from_rough_cut_plan(
        plan_file=plan_result["plan_file"],
        fps=fps,
        width=width,
        height=height,
    )
    if not timeline_result.get("success"):
        return _failed_step("create_timeline_from_rough_cut_plan", timeline_result, partial_outputs)

    saved_timeline = save_timeline(
        timeline=timeline_result["timeline"],
        output_directory=output_directory,
        name=f"{name}_timeline",
        overwrite=overwrite,
    )
    if not saved_timeline.get("success"):
        return _failed_step("save_timeline", saved_timeline, partial_outputs)
    partial_outputs["timeline"] = saved_timeline["timeline_file"]

    project_result = export_timeline_to_kdenlive_template(
        timeline_file=saved_timeline["timeline_file"],
        template_project=template_project,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        check_media_exists=True,
    )
    if not project_result.get("success"):
        return _failed_step("export_timeline_to_kdenlive_template", project_result, partial_outputs)
    partial_outputs["kdenlive_project"] = project_result["project"]

    warnings: list[dict[str, Any]] = []
    mlt_validation = {"checked": False, "valid": None}
    if check_mlt:
        mlt_validation = _validate_mlt_load(project_result["project"], timeout=mlt_timeout)
        if not mlt_validation.get("success"):
            return _failed_step("validate_mlt_load", mlt_validation, partial_outputs)
        if mlt_validation.get("valid") is None:
            warnings.append(
                {
                    "code": mlt_validation.get("warning", "MLT_VALIDATION_UNAVAILABLE"),
                    "message": "MLT load validation was requested but could not run in this environment.",
                }
            )

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
        "partial_outputs": partial_outputs,
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
            "mlt_load": mlt_validation,
        },
        "warnings": warnings,
    }
