from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument, TimelineTrack
from kdenlive_mcp.security import SecurityError, ensure_output_path
from kdenlive_mcp.services.manifest_service import slugify_name


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def timeline_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.timeline.json"


def _validate_rough_cut_plan(plan: Any) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must be a JSON object.")
    if plan.get("operation") != "plan_rough_cut":
        return _error("INVALID_ROUGH_CUT_PLAN", "Plan operation must be plan_rough_cut.")
    if plan.get("success") is not True:
        return _error("INVALID_ROUGH_CUT_PLAN", "Only successful rough cut plans can become timelines.")
    if plan.get("dry_run") is not True:
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must be a dry-run result.")
    if not isinstance(plan.get("segments"), list):
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must contain a segments array.")
    return None


def _extract_plan(data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if data.get("kind") == "kdenlive_mcp_rough_cut_plan":
        plan = data.get("plan")
        return plan if isinstance(plan, dict) else None, "kdenlive_mcp_rough_cut_plan"
    return data, None


def _clip_pair_for_segment(segment: dict[str, Any], index: int) -> tuple[TimelineClip, TimelineClip]:
    segment_id = str(segment.get("segment_id") or f"rough_{index:03d}")
    base_id = f"clip_{index:03d}"
    media = str(segment["media"])
    media_id = str(segment["media_id"])
    source_in = float(segment["source_in"])
    source_out = float(segment["source_out"])
    timeline_in = float(segment["timeline_in"])
    timeline_out = float(segment["timeline_out"])
    reason = segment.get("reason")

    video_clip = TimelineClip(
        id=f"{base_id}_v",
        track_id="track_v1",
        media_id=media_id,
        media=media,
        source_in=source_in,
        source_out=source_out,
        timeline_in=timeline_in,
        timeline_out=timeline_out,
        linked_clip_id=f"{base_id}_a",
        source_segment_id=segment_id,
        reason=reason,
    )
    audio_clip = TimelineClip(
        id=f"{base_id}_a",
        track_id="track_a1",
        media_id=media_id,
        media=media,
        source_in=source_in,
        source_out=source_out,
        timeline_in=timeline_in,
        timeline_out=timeline_out,
        linked_clip_id=f"{base_id}_v",
        source_segment_id=segment_id,
        reason=reason,
    )
    return video_clip, audio_clip


def timeline_from_rough_cut_plan(
    plan: dict[str, Any],
    fps: float = 30.0,
    width: int = 1080,
    height: int = 1920,
    source_plan_file: str | None = None,
    source_plan_kind: str | None = None,
) -> TimelineDocument:
    validation_error = _validate_rough_cut_plan(plan)
    if validation_error is not None:
        raise ValueError(validation_error["message"])

    tracks = [
        TimelineTrack(id="track_v1", type="video", name="Video 1"),
        TimelineTrack(id="track_a1", type="audio", name="Audio 1"),
    ]
    clips: list[TimelineClip] = []
    for index, segment in enumerate(plan["segments"], start=1):
        video_clip, audio_clip = _clip_pair_for_segment(segment, index)
        clips.extend([video_clip, audio_clip])

    return TimelineDocument(
        source_plan_file=source_plan_file,
        source_plan_kind=source_plan_kind,
        fps=fps,
        width=width,
        height=height,
        tracks=tracks,
        clips=clips,
    )


def save_timeline_document(path: Path, timeline: TimelineDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(timeline.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")


def load_timeline_document(path: Path) -> TimelineDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return TimelineDocument.model_validate(data)


def create_timeline_from_rough_cut_plan(
    plan_file: str,
    fps: float = 30.0,
    width: int = 1080,
    height: int = 1920,
) -> dict[str, Any]:
    try:
        path = ensure_output_path(plan_file)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("ROUGH_CUT_PLAN_NOT_FOUND", f"Rough cut plan does not exist: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _error("INVALID_ROUGH_CUT_PLAN", f"Rough cut plan JSON is invalid: {exc}")

    plan, plan_kind = _extract_plan(data)
    validation_error = _validate_rough_cut_plan(plan)
    if validation_error is not None:
        return validation_error

    try:
        timeline = timeline_from_rough_cut_plan(
            plan=plan,
            fps=fps,
            width=width,
            height=height,
            source_plan_file=str(path),
            source_plan_kind=plan_kind,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return _error("INVALID_TIMELINE", f"Could not build timeline: {exc}")

    return {
        "success": True,
        "operation": "create_timeline_from_rough_cut_plan",
        "timeline": timeline.model_dump(mode="json", exclude_none=True),
        "summary": {
            "track_count": len(timeline.tracks),
            "clip_count": len(timeline.clips),
            "duration": timeline.duration,
            "fps": timeline.fps,
            "width": timeline.width,
            "height": timeline.height,
        },
    }


def save_timeline(
    timeline: dict[str, Any],
    output_directory: str,
    name: str = "timeline",
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    path = timeline_path_for(output_dir, name)
    if path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"Timeline already exists: {path}")

    try:
        document = TimelineDocument.model_validate(timeline)
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")

    save_timeline_document(path, document)
    return {
        "success": True,
        "operation": "save_timeline",
        "timeline_file": str(path),
        "overwrite": overwrite,
        "summary": {
            "track_count": len(document.tracks),
            "clip_count": len(document.clips),
            "duration": document.duration,
        },
        "data": document.model_dump(mode="json", exclude_none=True),
    }


def inspect_timeline(timeline_file: str) -> dict[str, Any]:
    try:
        path = ensure_output_path(timeline_file)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("TIMELINE_NOT_FOUND", f"Timeline does not exist: {path}")

    try:
        document = load_timeline_document(path)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")

    return {
        "success": True,
        "operation": "inspect_timeline",
        "timeline_file": str(path),
        "summary": {
            "track_count": len(document.tracks),
            "clip_count": len(document.clips),
            "duration": document.duration,
        },
        "data": document.model_dump(mode="json", exclude_none=True),
    }
