from __future__ import annotations

import hashlib
from typing import Any

from kdenlive_mcp.tools.audio_tools import plan_silence_removal
from kdenlive_mcp.tools.media_tools import scan_media, validate_media


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _stable_media_id(path: str) -> str:
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f"media_{digest}"


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
}
