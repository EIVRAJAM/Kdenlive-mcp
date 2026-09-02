from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kdenlive_mcp.security import SecurityError, ensure_output_path
from kdenlive_mcp.services.manifest_service import slugify_name
from kdenlive_mcp.tools.audio_tools import plan_silence_removal
from kdenlive_mcp.tools.media_tools import scan_media, validate_media


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _stable_media_id(path: str) -> str:
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f"media_{digest}"


def _rough_cut_plan_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.rough-cut-plan.json"


def _validate_rough_cut_plan(plan: Any) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must be a JSON object.")
    if plan.get("operation") != "plan_rough_cut":
        return _error("INVALID_ROUGH_CUT_PLAN", "Plan operation must be plan_rough_cut.")
    if plan.get("success") is not True:
        return _error("INVALID_ROUGH_CUT_PLAN", "Only successful rough cut plans can be saved.")
    if plan.get("dry_run") is not True:
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must be a dry-run result.")
    if not isinstance(plan.get("segments"), list):
        return _error("INVALID_ROUGH_CUT_PLAN", "Rough cut plan must contain a segments array.")
    return None


def _plan_document(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "kdenlive_mcp_rough_cut_plan",
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
    }


def _validate_plan_document(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return _error("INVALID_ROUGH_CUT_PLAN", "Plan file must be a JSON object.")
    if data.get("kind") != "kdenlive_mcp_rough_cut_plan":
        return _error("INVALID_ROUGH_CUT_PLAN", "Unsupported rough cut plan kind.")
    if data.get("schema_version") != 1:
        return _error(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"Rough cut plan schema_version {data.get('schema_version')!r} is not supported; "
            "supported version is 1.",
        )
    return _validate_rough_cut_plan(data.get("plan"))


def _keep_segments_from_cuts(duration: float, cuts: list[dict[str, float]]) -> list[dict[str, float]]:
    segments: list[dict[str, float]] = []
    cursor = 0.0
    for cut in sorted(cuts, key=lambda item: item["start"]):
        start = max(0.0, min(duration, float(cut["start"])))
        end = max(0.0, min(duration, float(cut["end"])))
        if start > cursor:
            segments.append({"start": round(cursor, 6), "end": round(start, 6)})
        cursor = max(cursor, end)
    if cursor < duration:
        segments.append({"start": round(cursor, 6), "end": round(duration, 6)})
    return segments


def plan_rough_cut(
    folder: str,
    target_duration: float = 60.0,
    recursive: bool = True,
    max_files: int = 25,
    remove_silence: bool = True,
    silence_threshold_db: float = -35.0,
    silence_minimum_duration: float = 0.8,
    padding_before: float = 0.15,
    padding_after: float = 0.15,
    min_segment_duration: float = 0.25,
) -> dict[str, Any]:
    if target_duration <= 0:
        return _error("INVALID_ARGUMENT", "target_duration must be greater than zero.")
    if max_files < 1:
        return _error("INVALID_ARGUMENT", "max_files must be greater than zero.")
    if max_files > 500:
        return _error("INVALID_ARGUMENT", "max_files must be 500 or less.")
    if padding_before < 0 or padding_after < 0:
        return _error("INVALID_ARGUMENT", "padding_before and padding_after must be zero or greater.")
    if min_segment_duration <= 0:
        return _error("INVALID_ARGUMENT", "min_segment_duration must be greater than zero.")

    scan = scan_media(folder=folder, recursive=recursive, probe=False)
    if not scan.get("success"):
        return scan

    segments: list[dict[str, Any]] = []
    skipped_media: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    timeline_cursor = 0.0
    selected_media = scan.get("media", [])[:max_files]

    for item in selected_media:
        media_path = item["path"]
        validation = validate_media(media_path)
        if not validation.get("success"):
            failures.append({"media": media_path, **validation})
            continue
        if not validation.get("valid"):
            skipped_media.append({"media": media_path, "reason": "INVALID_MEDIA"})
            continue
        if not validation.get("has_video"):
            skipped_media.append({"media": media_path, "reason": "NO_VIDEO_STREAM"})
            continue

        duration_value = validation["media"].get("duration_seconds")
        if duration_value is None:
            failures.append({"media": media_path, "error": "MEDIA_DURATION_UNKNOWN"})
            continue
        media_duration = float(duration_value)

        cuts: list[dict[str, float]] = []
        silence_cut_count = 0
        if remove_silence and validation.get("has_audio"):
            silence_plan = plan_silence_removal(
                media=media_path,
                threshold_db=silence_threshold_db,
                minimum_duration=silence_minimum_duration,
                padding_before=padding_before,
                padding_after=padding_after,
            )
            if not silence_plan.get("success"):
                failures.append({"media": media_path, **silence_plan})
                continue
            cuts = silence_plan["cuts"]
            silence_cut_count = silence_plan["cut_count"]

        media_id = _stable_media_id(media_path)
        for keep in _keep_segments_from_cuts(media_duration, cuts):
            if timeline_cursor >= target_duration:
                break
            source_in = keep["start"]
            source_out = keep["end"]
            segment_duration = source_out - source_in
            if segment_duration < min_segment_duration:
                continue
            remaining = target_duration - timeline_cursor
            planned_duration = min(segment_duration, remaining)
            if planned_duration < min_segment_duration:
                continue
            segment_id = f"rough_{len(segments) + 1:03d}"
            segments.append(
                {
                    "segment_id": segment_id,
                    "media_id": media_id,
                    "media": media_path,
                    "source_in": round(source_in, 6),
                    "source_out": round(source_in + planned_duration, 6),
                    "duration": round(planned_duration, 6),
                    "timeline_in": round(timeline_cursor, 6),
                    "timeline_out": round(timeline_cursor + planned_duration, 6),
                    "reason": "silence_removed" if silence_cut_count else "sequential_selection",
                }
            )
            timeline_cursor = round(timeline_cursor + planned_duration, 6)
        if timeline_cursor >= target_duration:
            break

    return {
        "success": len(failures) == 0,
        "operation": "plan_rough_cut",
        "dry_run": True,
        "folder": scan["folder"],
        "recursive": recursive,
        "target_duration": float(target_duration),
        "planned_duration": round(timeline_cursor, 6),
        "total_media_count": scan["count"],
        "analyzed_media_count": len(selected_media),
        "selected_segment_count": len(segments),
        "skipped_media_count": len(skipped_media),
        "failure_count": len(failures),
        "remove_silence": remove_silence,
        "segments": segments,
        "skipped_media": skipped_media,
        "failures": failures,
    }


def save_rough_cut_plan(
    plan: dict[str, Any],
    output_directory: str,
    name: str = "rough_cut_plan",
    overwrite: bool = False,
) -> dict[str, Any]:
    validation_error = _validate_rough_cut_plan(plan)
    if validation_error is not None:
        return validation_error
    try:
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)

    path = _rough_cut_plan_path_for(output_dir, name)
    if path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"Rough cut plan already exists: {path}")

    document = _plan_document(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "success": True,
        "operation": "save_rough_cut_plan",
        "plan_file": str(path),
        "overwrite": overwrite,
        "data": document,
    }


def inspect_rough_cut_plan(plan_file: str) -> dict[str, Any]:
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
    validation_error = _validate_plan_document(data)
    if validation_error is not None:
        return validation_error
    return {
        "success": True,
        "operation": "inspect_rough_cut_plan",
        "plan_file": str(path),
        "data": data,
    }


def create_rough_cut_plan_file(
    folder: str,
    output_directory: str,
    name: str = "rough_cut_plan",
    overwrite: bool = False,
    target_duration: float = 60.0,
    recursive: bool = True,
    max_files: int = 25,
    remove_silence: bool = True,
    silence_threshold_db: float = -35.0,
    silence_minimum_duration: float = 0.8,
    padding_before: float = 0.15,
    padding_after: float = 0.15,
    min_segment_duration: float = 0.25,
) -> dict[str, Any]:
    plan = plan_rough_cut(
        folder=folder,
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
    if not plan.get("success"):
        return plan

    saved = save_rough_cut_plan(
        plan=plan,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
    )
    if not saved.get("success"):
        return saved
    return {
        "success": True,
        "operation": "create_rough_cut_plan_file",
        "plan_file": saved["plan_file"],
        "plan": plan,
        "data": saved["data"],
    }


TOOLS: dict[str, dict[str, Any]] = {
    "plan_rough_cut": {
        "description": "Build a read-only dry-run rough-cut segment plan from media in an allowed folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "target_duration": {"type": "number", "default": 60.0},
                "recursive": {"type": "boolean", "default": True},
                "max_files": {"type": "integer", "default": 25},
                "remove_silence": {"type": "boolean", "default": True},
                "silence_threshold_db": {"type": "number", "default": -35.0},
                "silence_minimum_duration": {"type": "number", "default": 0.8},
                "padding_before": {"type": "number", "default": 0.15},
                "padding_after": {"type": "number", "default": 0.15},
                "min_segment_duration": {"type": "number", "default": 0.25},
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
        "handler": plan_rough_cut,
    },
    "save_rough_cut_plan": {
        "description": "Persist a successful dry-run rough-cut plan into an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plan": {"type": "object"},
                "output_directory": {"type": "string"},
                "name": {"type": "string", "default": "rough_cut_plan"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["plan", "output_directory"],
            "additionalProperties": False,
        },
        "handler": save_rough_cut_plan,
    },
    "inspect_rough_cut_plan": {
        "description": "Load and validate a persisted rough-cut plan JSON file.",
        "inputSchema": {
            "type": "object",
            "properties": {"plan_file": {"type": "string"}},
            "required": ["plan_file"],
            "additionalProperties": False,
        },
        "handler": inspect_rough_cut_plan,
    },
    "create_rough_cut_plan_file": {
        "description": "Create a dry-run rough-cut plan and persist it into an allowed output directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string"},
                "output_directory": {"type": "string"},
                "name": {"type": "string", "default": "rough_cut_plan"},
                "overwrite": {"type": "boolean", "default": False},
                "target_duration": {"type": "number", "default": 60.0},
                "recursive": {"type": "boolean", "default": True},
                "max_files": {"type": "integer", "default": 25},
                "remove_silence": {"type": "boolean", "default": True},
                "silence_threshold_db": {"type": "number", "default": -35.0},
                "silence_minimum_duration": {"type": "number", "default": 0.8},
                "padding_before": {"type": "number", "default": 0.15},
                "padding_after": {"type": "number", "default": 0.15},
                "min_segment_duration": {"type": "number", "default": 0.25},
            },
            "required": ["folder", "output_directory"],
            "additionalProperties": False,
        },
        "handler": create_rough_cut_plan_file,
    },
}
