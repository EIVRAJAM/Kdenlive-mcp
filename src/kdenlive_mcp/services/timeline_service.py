from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kdenlive_mcp.adapters.mlt_xml import write_mlt_xml
from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument, TimelineMarker, TimelineTrack
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path, ensure_project_path
from kdenlive_mcp.services.manifest_service import slugify_name


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def timeline_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.timeline.json"


def mlt_xml_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.mlt.xml"


def kdenlive_project_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.kdenlive"


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
    markers: list[TimelineMarker] = []
    for index, segment in enumerate(plan["segments"], start=1):
        video_clip, audio_clip = _clip_pair_for_segment(segment, index)
        clips.extend([video_clip, audio_clip])
        markers.append(
            TimelineMarker(
                id=f"marker_{index:03d}",
                comment=str(segment.get("segment_id") or f"rough_{index:03d}"),
                position=float(segment["timeline_in"]),
                duration=round(float(segment["timeline_out"]) - float(segment["timeline_in"]), 6),
                type=0,
            )
        )

    return TimelineDocument(
        source_plan_file=source_plan_file,
        source_plan_kind=source_plan_kind,
        fps=fps,
        width=width,
        height=height,
        tracks=tracks,
        clips=clips,
        markers=markers,
    )


def save_timeline_document(path: Path, timeline: TimelineDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(timeline.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8")


def load_timeline_document(path: Path) -> TimelineDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return TimelineDocument.model_validate(data)


def validate_timeline_document(
    document: TimelineDocument,
    check_media_exists: bool = True,
    duration_tolerance: float = 0.001,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    clips_by_id = {clip.id: clip for clip in document.clips}
    for track in document.tracks:
        track_clips = sorted(
            [clip for clip in document.clips if clip.track_id == track.id],
            key=lambda clip: (clip.timeline_in, clip.timeline_out, clip.id),
        )
        previous = None
        for clip in track_clips:
            if previous is not None and clip.timeline_in < previous.timeline_out - duration_tolerance:
                issues.append(
                    {
                        "code": "TIMELINE_OVERLAP",
                        "track_id": track.id,
                        "clip_id": clip.id,
                        "previous_clip_id": previous.id,
                        "overlap_start": round(clip.timeline_in, 6),
                        "overlap_end": round(previous.timeline_out, 6),
                    }
                )
            previous = clip

    for clip in document.clips:
        source_duration = round((clip.source_out - clip.source_in) / clip.speed, 6)
        timeline_duration = clip.duration
        if abs(source_duration - timeline_duration) > duration_tolerance:
            issues.append(
                {
                    "code": "DURATION_MISMATCH",
                    "clip_id": clip.id,
                    "source_duration": source_duration,
                    "timeline_duration": timeline_duration,
                    "speed": clip.speed,
                }
            )

        linked_clip = clips_by_id.get(clip.linked_clip_id or "")
        if linked_clip is not None:
            linked_fields_match = (
                clip.media_id == linked_clip.media_id
                and clip.media == linked_clip.media
                and abs(clip.source_in - linked_clip.source_in) <= duration_tolerance
                and abs(clip.source_out - linked_clip.source_out) <= duration_tolerance
                and abs(clip.timeline_in - linked_clip.timeline_in) <= duration_tolerance
                and abs(clip.timeline_out - linked_clip.timeline_out) <= duration_tolerance
            )
            if not linked_fields_match:
                issues.append(
                    {
                        "code": "LINKED_CLIP_MISMATCH",
                        "clip_id": clip.id,
                        "linked_clip_id": linked_clip.id,
                    }
                )

        if check_media_exists:
            try:
                media_path = ensure_media_path(clip.media)
            except SecurityError as exc:
                issues.append(
                    {
                        "code": exc.code,
                        "clip_id": clip.id,
                        "media": clip.media,
                        "message": exc.message,
                    }
                )
                continue
            if not media_path.exists():
                issues.append(
                    {
                        "code": "MEDIA_OFFLINE",
                        "clip_id": clip.id,
                        "media": str(media_path),
                    }
                )
    return {
        "valid": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
        "summary": {
            "track_count": len(document.tracks),
            "clip_count": len(document.clips),
            "marker_count": len(document.markers),
            "duration": document.duration,
            "check_media_exists": check_media_exists,
            "duration_tolerance": duration_tolerance,
        },
    }


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
            "marker_count": len(timeline.markers),
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
    validation = validate_timeline_document(document, check_media_exists=False)
    if not validation["valid"]:
        return _error("INVALID_TIMELINE", "Timeline validation failed.", validation=validation)

    save_timeline_document(path, document)
    return {
        "success": True,
        "operation": "save_timeline",
        "timeline_file": str(path),
        "overwrite": overwrite,
        "summary": {
            "track_count": len(document.tracks),
            "clip_count": len(document.clips),
            "marker_count": len(document.markers),
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
            "marker_count": len(document.markers),
            "duration": document.duration,
        },
        "data": document.model_dump(mode="json", exclude_none=True),
    }


def validate_timeline(
    timeline_file: str,
    check_media_exists: bool = True,
    duration_tolerance: float = 0.001,
) -> dict[str, Any]:
    if duration_tolerance < 0:
        return _error("INVALID_ARGUMENT", "duration_tolerance must be zero or greater.")
    inspected = inspect_timeline(timeline_file)
    if not inspected.get("success"):
        return inspected
    try:
        document = TimelineDocument.model_validate(inspected["data"])
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")
    validation = validate_timeline_document(
        document,
        check_media_exists=check_media_exists,
        duration_tolerance=duration_tolerance,
    )
    return {
        "success": True,
        "operation": "validate_timeline",
        "timeline_file": inspected["timeline_file"],
        **validation,
    }


def export_timeline_to_mlt_xml(
    timeline_file: str,
    output_directory: str,
    name: str = "timeline_draft",
    overwrite: bool = False,
    check_media_exists: bool = True,
) -> dict[str, Any]:
    try:
        timeline_path = ensure_output_path(timeline_file)
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    if not timeline_path.exists():
        return _error("TIMELINE_NOT_FOUND", f"Timeline does not exist: {timeline_path}")

    output_path = mlt_xml_path_for(output_dir, name)
    if output_path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"MLT XML draft already exists: {output_path}")

    try:
        document = load_timeline_document(timeline_path)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")

    validation = validate_timeline_document(document, check_media_exists=check_media_exists)
    if not validation["valid"]:
        return _error("INVALID_TIMELINE", "Timeline validation failed.", validation=validation)

    try:
        write_mlt_xml(output_path, document)
    except ValueError as exc:
        return _error("MLT_XML_ERROR", f"Could not export MLT XML: {exc}")

    return {
        "success": True,
        "operation": "export_timeline_to_mlt_xml",
        "timeline_file": str(timeline_path),
        "mlt_xml": str(output_path),
        "format": "mlt_xml_draft",
        "kdenlive_project": False,
        "summary": validation["summary"],
    }


def export_timeline_to_kdenlive_template(
    timeline_file: str,
    template_project: str,
    output_directory: str,
    name: str = "timeline_draft",
    overwrite: bool = False,
    check_media_exists: bool = True,
) -> dict[str, Any]:
    try:
        timeline_path = ensure_output_path(timeline_file)
        template_path = ensure_project_path(template_project)
        output_dir = ensure_project_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    if not timeline_path.exists():
        return _error("TIMELINE_NOT_FOUND", f"Timeline does not exist: {timeline_path}")
    if not template_path.exists():
        return _error("PROJECT_NOT_FOUND", f"Template project does not exist: {template_path}")

    output_path = kdenlive_project_path_for(output_dir, name)
    if output_path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"Kdenlive project already exists: {output_path}")

    try:
        document = load_timeline_document(timeline_path)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")

    validation = validate_timeline_document(document, check_media_exists=check_media_exists)
    if not validation["valid"]:
        return _error("INVALID_TIMELINE", "Timeline validation failed.", validation=validation)

    adapter = KdenliveProjectAdapter()
    try:
        write_result = adapter.write_timeline_from_template(template_path, output_path, document)
        inspection = adapter.inspect(output_path)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)

    missing_media_count = inspection["validation"]["missing_media_count"]
    return {
        "success": missing_media_count == 0,
        "operation": "export_timeline_to_kdenlive_template",
        "project": str(output_path),
        "template_project": str(template_path),
        "format": "kdenlive_template_draft",
        "kdenlive_project": True,
        "write_result": write_result,
        "inspection_summary": {
            "bin_media_count": inspection["bin"]["media_count"],
            "sequence_count": len(inspection["sequences"]),
            "active_sequence_id": inspection["active_sequence_id"],
            "timeline_clip_count": sum(sequence["timeline_clip_count"] for sequence in inspection["sequences"]),
            "marker_count": sum(len(sequence["markers"]) for sequence in inspection["sequences"]),
            "guide_count": sum(len(sequence["guides"]) for sequence in inspection["sequences"]),
            "missing_media_count": missing_media_count,
        },
        "validation": validation,
    }
