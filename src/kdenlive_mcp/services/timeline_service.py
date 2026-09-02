from __future__ import annotations

import json
import hashlib
import math
import re
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


SUPPORTED_TIMELINE_SCHEMA_VERSION = 1


class UnsupportedSchemaVersion(ValueError):
    pass


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def _coerce_finite_float(value: Any, field_name: str) -> float | dict[str, Any]:
    if isinstance(value, bool):
        return _error("INVALID_TIMECODE", f"{field_name} must be a finite number.", field=field_name)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _error("INVALID_TIMECODE", f"{field_name} must be a finite number.", field=field_name)
    if math.isnan(number) or math.isinf(number):
        return _error("INVALID_TIMECODE", f"{field_name} must be a finite number.", field=field_name)
    return number


def timeline_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.timeline.json"


def mlt_xml_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.mlt.xml"


def kdenlive_project_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.kdenlive"


def _timeline_summary(document: TimelineDocument) -> dict[str, Any]:
    return {
        "track_count": len(document.tracks),
        "clip_count": len(document.clips),
        "marker_count": len(document.markers),
        "duration": document.duration,
    }


def _load_timeline_from_allowed_output(timeline_file: str) -> tuple[Path, TimelineDocument] | dict[str, Any]:
    try:
        path = ensure_output_path(timeline_file)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("TIMELINE_NOT_FOUND", f"Timeline does not exist: {path}")
    try:
        return path, load_timeline_document(path)
    except UnsupportedSchemaVersion as exc:
        return _error("UNSUPPORTED_SCHEMA_VERSION", str(exc))
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_TIMELINE", f"Timeline is invalid: {exc}")


def _clip_map(document: TimelineDocument) -> dict[str, TimelineClip]:
    return {clip.id: clip for clip in document.clips}


def _track_map(document: TimelineDocument) -> dict[str, TimelineTrack]:
    return {track.id: track for track in document.tracks}


def _next_track_id(document: TimelineDocument, track_type: str) -> str:
    prefix = "track_v" if track_type == "video" else "track_a"
    existing = {track.id for track in document.tracks}
    index = 1
    while f"{prefix}{index}" in existing:
        index += 1
    return f"{prefix}{index}"


def _next_clip_base(document: TimelineDocument) -> str:
    index = 1
    for clip in document.clips:
        match = re.match(r"^clip_(\d{3,})_", clip.id)
        if match:
            index = max(index, int(match.group(1)) + 1)
    return f"clip_{index:03d}"


def _edit_target_ids(document: TimelineDocument, clip_id: str, include_linked: bool) -> list[str] | dict[str, Any]:
    clips_by_id = _clip_map(document)
    clip = clips_by_id.get(clip_id)
    if clip is None:
        return _error("INVALID_CLIP", f"Clip does not exist: {clip_id}")
    target_ids = [clip.id]
    if include_linked and clip.linked_clip_id:
        linked_clip = clips_by_id.get(clip.linked_clip_id)
        if linked_clip is None:
            return _error("INVALID_CLIP", f"Linked clip does not exist: {clip.linked_clip_id}")
        target_ids.append(linked_clip.id)
    return target_ids


def _unique_clip_id(existing_ids: set[str], base: str) -> str:
    candidate = base
    suffix = 1
    while candidate in existing_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"
    existing_ids.add(candidate)
    return candidate


def _maybe_write_edited_timeline(
    *,
    operation: str,
    source_path: Path,
    document: TimelineDocument,
    output_directory: str | None,
    name: str | None,
    overwrite: bool,
    dry_run: bool,
    before: dict[str, Any],
    after: dict[str, Any],
    check_media_exists: bool,
) -> dict[str, Any]:
    validation = validate_timeline_document(document, check_media_exists=check_media_exists)
    output_path: Path | None = None
    if output_directory is not None or name is not None:
        try:
            output_dir = ensure_output_path(output_directory or str(source_path.parent))
        except SecurityError as exc:
            return _security_error(exc)
        output_path = timeline_path_for(output_dir, name or f"{source_path.stem}_{operation}")
        if output_path.exists() and not overwrite and not dry_run:
            return _error("OUTPUT_EXISTS", f"Timeline already exists: {output_path}")

    result = {
        "success": validation["valid"],
        "operation": operation,
        "dry_run": dry_run,
        "source_timeline_file": str(source_path),
        "timeline_file": None if dry_run else str(output_path) if output_path else None,
        "would_write": str(output_path) if output_path else None,
        "before": before,
        "after": after,
        "summary": _timeline_summary(document),
        "validation": validation,
        "timeline": document.model_dump(mode="json", exclude_none=True),
    }
    if not validation["valid"]:
        result.update(
            {
                "success": False,
                "error": "INVALID_TIMELINE",
                "message": "Edited timeline validation failed.",
            }
        )
        return result
    if dry_run:
        return result
    if output_path is None:
        return _error("INVALID_ARGUMENT", "output_directory or name is required when dry_run is false.")
    save_timeline_document(output_path, document)
    return result


def _trim_document_clip(
    document: TimelineDocument,
    clip_id: str,
    source_in: float | None,
    source_out: float | None,
    include_linked: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    if source_in is None and source_out is None:
        return _error("INVALID_ARGUMENT", "source_in or source_out is required.")

    target_ids = _edit_target_ids(document, clip_id, include_linked)
    if isinstance(target_ids, dict):
        return target_ids
    edited = document.model_copy(deep=True)
    clips_by_id = _clip_map(edited)
    before = {"clips": {target_id: clips_by_id[target_id].model_dump(mode="json", exclude_none=True) for target_id in target_ids}}

    for target_id in target_ids:
        clip = clips_by_id[target_id]
        new_source_in = clip.source_in if source_in is None else float(source_in)
        new_source_out = clip.source_out if source_out is None else float(source_out)
        if new_source_in < 0:
            return _error("INVALID_TIMECODE", "source_in must be zero or greater.", clip_id=target_id)
        if new_source_out <= new_source_in:
            return _error("INVALID_TIMECODE", "source_out must be greater than source_in.", clip_id=target_id)
        new_duration = round((new_source_out - new_source_in) / clip.speed, 6)
        old_duration = clip.duration
        if new_duration > old_duration:
            return _error(
                "INVALID_TIMECODE",
                "trim_timeline_clip cannot extend a clip; use move/add operations for expansion.",
                clip_id=target_id,
                old_duration=old_duration,
                requested_duration=new_duration,
            )
        clip.source_in = new_source_in
        clip.source_out = new_source_out
        clip.timeline_out = round(clip.timeline_in + new_duration, 6)

    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after_clips = _clip_map(edited)
    after = {"clips": {target_id: after_clips[target_id].model_dump(mode="json", exclude_none=True) for target_id in target_ids}}
    return edited, before, after


def _move_document_clip(
    document: TimelineDocument,
    clip_id: str,
    timeline_in: float,
    include_linked: bool,
    move_markers: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    if timeline_in < 0:
        return _error("INVALID_TIMECODE", "timeline_in must be zero or greater.")

    target_ids = _edit_target_ids(document, clip_id, include_linked)
    if isinstance(target_ids, dict):
        return target_ids
    edited = document.model_copy(deep=True)
    clips_by_id = _clip_map(edited)
    primary = clips_by_id[clip_id]
    original_timeline_in = primary.timeline_in
    original_timeline_out = primary.timeline_out
    delta = round(float(timeline_in) - primary.timeline_in, 6)
    before = {
        "clips": {target_id: clips_by_id[target_id].model_dump(mode="json", exclude_none=True) for target_id in target_ids},
        "markers": [
            marker.model_dump(mode="json", exclude_none=True)
            for marker in edited.markers
            if original_timeline_in <= marker.position < original_timeline_out
        ],
    }

    for target_id in target_ids:
        clip = clips_by_id[target_id]
        clip.timeline_in = round(clip.timeline_in + delta, 6)
        clip.timeline_out = round(clip.timeline_out + delta, 6)
    if move_markers:
        for marker in edited.markers:
            if original_timeline_in <= marker.position < original_timeline_out:
                marker.position = round(marker.position + delta, 6)

    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after_clips = _clip_map(edited)
    moved_primary = after_clips[clip_id]
    after = {
        "clips": {target_id: after_clips[target_id].model_dump(mode="json", exclude_none=True) for target_id in target_ids},
        "markers": [
            marker.model_dump(mode="json", exclude_none=True)
            for marker in edited.markers
            if moved_primary.timeline_in <= marker.position < moved_primary.timeline_out
        ],
        "delta": delta,
    }
    return edited, before, after


def _split_document_clip(
    document: TimelineDocument,
    clip_id: str,
    split_at: float,
    include_linked: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    target_ids = _edit_target_ids(document, clip_id, include_linked)
    if isinstance(target_ids, dict):
        return target_ids
    clips_by_id = _clip_map(document)
    primary = clips_by_id[clip_id]
    split_at = float(split_at)
    if split_at <= primary.timeline_in or split_at >= primary.timeline_out:
        return _error(
            "INVALID_TIMECODE",
            "split_at must be inside the clip timeline range.",
            clip_id=clip_id,
            timeline_in=primary.timeline_in,
            timeline_out=primary.timeline_out,
        )

    edited = document.model_copy(deep=True)
    existing_ids = {clip.id for clip in edited.clips}
    before = {"clips": {target_id: _clip_map(edited)[target_id].model_dump(mode="json", exclude_none=True) for target_id in target_ids}}
    replacements: dict[str, tuple[TimelineClip, TimelineClip]] = {}
    for target_id in target_ids:
        clip = _clip_map(edited)[target_id]
        source_split = round(clip.source_in + ((split_at - clip.timeline_in) * clip.speed), 6)
        first_id = _unique_clip_id(existing_ids, f"{clip.id}_part1")
        second_id = _unique_clip_id(existing_ids, f"{clip.id}_part2")
        first = clip.model_copy(deep=True)
        second = clip.model_copy(deep=True)
        first.id = first_id
        first.source_out = source_split
        first.timeline_out = split_at
        second.id = second_id
        second.source_in = source_split
        second.timeline_in = split_at
        replacements[target_id] = (first, second)

    if len(target_ids) == 2:
        first_a, second_a = replacements[target_ids[0]]
        first_b, second_b = replacements[target_ids[1]]
        first_a.linked_clip_id = first_b.id
        first_b.linked_clip_id = first_a.id
        second_a.linked_clip_id = second_b.id
        second_b.linked_clip_id = second_a.id
    elif len(target_ids) == 1:
        first, second = replacements[target_ids[0]]
        first.linked_clip_id = None
        second.linked_clip_id = None

    new_clips: list[TimelineClip] = []
    for clip in edited.clips:
        replacement = replacements.get(clip.id)
        if replacement is None:
            new_clips.append(clip)
        else:
            new_clips.extend(replacement)
    edited.clips = new_clips

    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after_clip_ids = [clip.id for pair in replacements.values() for clip in pair]
    after_clips = _clip_map(edited)
    after = {
        "split_at": split_at,
        "clips": {target_id: after_clips[target_id].model_dump(mode="json", exclude_none=True) for target_id in after_clip_ids},
    }
    return edited, before, after


def _create_document_track(
    document: TimelineDocument,
    track_type: str,
    name: str | None,
    track_id: str | None,
    position: int | None,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    if track_type not in {"video", "audio"}:
        return _error("INVALID_TRACK", "track_type must be video or audio.")
    edited = document.model_copy(deep=True)
    candidate_id = track_id or _next_track_id(edited, track_type)
    if not candidate_id.strip():
        return _error("INVALID_TRACK", "track_id must not be empty.")
    if candidate_id in _track_map(edited):
        return _error("INVALID_TRACK", f"Track already exists: {candidate_id}")
    default_name = f"{track_type.title()} {sum(1 for track in edited.tracks if track.type == track_type) + 1}"
    track_name = name or default_name
    if not track_name.strip():
        return _error("INVALID_TRACK", "Track name must not be empty.")
    track = TimelineTrack(id=candidate_id, type=track_type, name=track_name)
    before = {"tracks": [item.model_dump(mode="json", exclude_none=True) for item in edited.tracks]}
    if position is None:
        edited.tracks.append(track)
    else:
        if position < 0 or position > len(edited.tracks):
            return _error("INVALID_TRACK", "position must be within the timeline track range.")
        edited.tracks.insert(position, track)
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {"track": track.model_dump(mode="json", exclude_none=True), "position": position}
    return edited, before, after


def _update_document_track(
    document: TimelineDocument,
    track_id: str,
    name: str | None,
    locked: bool | None,
    muted: bool | None,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    edited = document.model_copy(deep=True)
    tracks_by_id = _track_map(edited)
    track = tracks_by_id.get(track_id)
    if track is None:
        return _error("INVALID_TRACK", f"Track does not exist: {track_id}")
    before = {"track": track.model_dump(mode="json", exclude_none=True)}
    if name is not None:
        if not name.strip():
            return _error("INVALID_TRACK", "Track name must not be empty.")
        track.name = name
    if locked is not None:
        track.locked = bool(locked)
    if muted is not None:
        track.muted = bool(muted)
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {"track": _track_map(edited)[track_id].model_dump(mode="json", exclude_none=True)}
    return edited, before, after


def _remove_document_track(
    document: TimelineDocument,
    track_id: str,
    remove_clips: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    edited = document.model_copy(deep=True)
    tracks_by_id = _track_map(edited)
    track = tracks_by_id.get(track_id)
    if track is None:
        return _error("INVALID_TRACK", f"Track does not exist: {track_id}")
    clips_on_track = [clip for clip in edited.clips if clip.track_id == track_id]
    if clips_on_track and not remove_clips:
        return _error(
            "TRACK_NOT_EMPTY",
            "Track contains clips. Set remove_clips=true to remove the track and its clips.",
            track_id=track_id,
            clip_count=len(clips_on_track),
        )
    removed_clip_ids = {clip.id for clip in clips_on_track}
    before = {
        "track": track.model_dump(mode="json", exclude_none=True),
        "removed_clips": [clip.model_dump(mode="json", exclude_none=True) for clip in clips_on_track],
    }
    edited.tracks = [item for item in edited.tracks if item.id != track_id]
    if remove_clips:
        edited.clips = [clip for clip in edited.clips if clip.track_id != track_id]
        for clip in edited.clips:
            if clip.linked_clip_id in removed_clip_ids:
                clip.linked_clip_id = None
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {"removed_track_id": track_id, "removed_clip_count": len(clips_on_track)}
    return edited, before, after


def _add_document_clip(
    document: TimelineDocument,
    track_id: str,
    media: str,
    source_in: float,
    source_out: float,
    timeline_in: float,
    media_id: str | None,
    clip_id: str | None,
    speed: float,
    create_linked_clip: bool,
    linked_track_id: str | None,
    source_segment_id: str | None,
    reason: str | None,
    require_media_exists: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    try:
        media_path = ensure_media_path(media)
    except SecurityError as exc:
        return _security_error(exc)
    if require_media_exists and not media_path.exists():
        return _error("MEDIA_NOT_FOUND", f"Media file does not exist: {media_path}", media=str(media_path))

    tracks_by_id = _track_map(document)
    track = tracks_by_id.get(track_id)
    if track is None:
        return _error("INVALID_TRACK", f"Track does not exist: {track_id}")
    if source_in < 0 or timeline_in < 0:
        return _error("INVALID_TIMECODE", "source_in and timeline_in must be zero or greater.")
    if source_out <= source_in:
        return _error("INVALID_TIMECODE", "source_out must be greater than source_in.")
    if speed <= 0:
        return _error("INVALID_TIMECODE", "speed must be greater than zero.")

    edited = document.model_copy(deep=True)
    existing_ids = {clip.id for clip in edited.clips}
    base = _next_clip_base(edited)
    suffix = "_a" if track.type == "audio" else "_v"
    primary_id = clip_id or f"{base}{suffix}"
    if primary_id in existing_ids:
        return _error("INVALID_CLIP", f"Clip already exists: {primary_id}")
    existing_ids.add(primary_id)
    final_media_id = media_id or f"media_{hashlib.sha1(str(media_path.resolve(strict=False)).encode('utf-8')).hexdigest()[:12]}"
    duration = round((source_out - source_in) / speed, 6)
    primary = TimelineClip(
        id=primary_id,
        track_id=track_id,
        media_id=final_media_id,
        media=str(media_path),
        source_in=float(source_in),
        source_out=float(source_out),
        timeline_in=float(timeline_in),
        timeline_out=round(float(timeline_in) + duration, 6),
        speed=float(speed),
        source_segment_id=source_segment_id,
        reason=reason,
    )
    added = [primary]

    if create_linked_clip:
        if linked_track_id is None:
            opposite_type = "audio" if track.type == "video" else "video"
            linked_track = next((item for item in edited.tracks if item.type == opposite_type), None)
        else:
            linked_track = tracks_by_id.get(linked_track_id)
        if linked_track is None:
            return _error("INVALID_TRACK", "A linked track could not be resolved.")
        if linked_track.type == track.type:
            return _error("INVALID_TRACK", "Linked track must be the opposite media type.")
        linked_suffix = "_a" if linked_track.type == "audio" else "_v"
        linked_id = _unique_clip_id(existing_ids, f"{base}{linked_suffix}")
        linked = primary.model_copy(deep=True)
        linked.id = linked_id
        linked.track_id = linked_track.id
        primary.linked_clip_id = linked.id
        linked.linked_clip_id = primary.id
        added.append(linked)

    before = {"clip_count": len(edited.clips)}
    edited.clips.extend(added)
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {"clips": {clip.id: clip.model_dump(mode="json", exclude_none=True) for clip in added}}
    return edited, before, after


def _remove_document_clip(
    document: TimelineDocument,
    clip_id: str,
    include_linked: bool,
    remove_markers: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    target_ids = _edit_target_ids(document, clip_id, include_linked)
    if isinstance(target_ids, dict):
        return target_ids
    edited = document.model_copy(deep=True)
    clips_by_id = _clip_map(edited)
    removed = [clips_by_id[target_id] for target_id in target_ids]
    removed_ids = {clip.id for clip in removed}
    marker_ranges = [(clip.timeline_in, clip.timeline_out) for clip in removed]
    before = {"clips": {clip.id: clip.model_dump(mode="json", exclude_none=True) for clip in removed}}
    edited.clips = [clip for clip in edited.clips if clip.id not in removed_ids]
    for clip in edited.clips:
        if clip.linked_clip_id in removed_ids:
            clip.linked_clip_id = None
    removed_markers: list[TimelineMarker] = []
    if remove_markers:
        kept_markers: list[TimelineMarker] = []
        for marker in edited.markers:
            if any(start <= marker.position < end for start, end in marker_ranges):
                removed_markers.append(marker)
            else:
                kept_markers.append(marker)
        edited.markers = kept_markers
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {
        "removed_clip_ids": sorted(removed_ids),
        "removed_marker_ids": [marker.id for marker in removed_markers],
        "clip_count": len(edited.clips),
    }
    return edited, before, after


def _duplicate_document_clip(
    document: TimelineDocument,
    clip_id: str,
    timeline_in: float | None,
    new_clip_id: str | None,
    include_linked: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    target_ids = _edit_target_ids(document, clip_id, include_linked)
    if isinstance(target_ids, dict):
        return target_ids
    if timeline_in is not None and timeline_in < 0:
        return _error("INVALID_TIMECODE", "timeline_in must be zero or greater.")

    edited = document.model_copy(deep=True)
    clips_by_id = _clip_map(edited)
    originals = [clips_by_id[target_id] for target_id in target_ids]
    primary = clips_by_id[clip_id]
    destination_start = document.duration if timeline_in is None else float(timeline_in)
    delta = round(destination_start - primary.timeline_in, 6)
    existing_ids = {clip.id for clip in edited.clips}
    base = _next_clip_base(edited)
    duplicates: list[TimelineClip] = []

    for original in originals:
        duplicate = original.model_copy(deep=True)
        if original.id == clip_id and new_clip_id:
            if new_clip_id in existing_ids:
                return _error("INVALID_CLIP", f"Clip already exists: {new_clip_id}")
            duplicate.id = new_clip_id
            existing_ids.add(new_clip_id)
        else:
            suffix = "_a" if _track_map(edited)[original.track_id].type == "audio" else "_v"
            duplicate.id = _unique_clip_id(existing_ids, f"{base}{suffix}")
        duplicate.timeline_in = round(original.timeline_in + delta, 6)
        duplicate.timeline_out = round(original.timeline_out + delta, 6)
        duplicate.linked_clip_id = None
        duplicates.append(duplicate)

    if len(duplicates) == 2:
        duplicates[0].linked_clip_id = duplicates[1].id
        duplicates[1].linked_clip_id = duplicates[0].id

    before = {"clips": {clip.id: clip.model_dump(mode="json", exclude_none=True) for clip in originals}}
    edited.clips.extend(duplicates)
    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    after = {
        "clips": {clip.id: clip.model_dump(mode="json", exclude_none=True) for clip in duplicates},
        "delta": delta,
    }
    return edited, before, after


def _gap_track_ids(
    document: TimelineDocument,
    track_ids: Any,
    track_type: str | None,
) -> list[str] | dict[str, Any]:
    tracks_by_id = _track_map(document)
    if track_type is not None and track_type not in {"video", "audio"}:
        return _error("INVALID_TRACK", "track_type must be video or audio.")
    if track_ids is not None:
        if not isinstance(track_ids, list) or len(track_ids) == 0 or any(
            not isinstance(track_id, str) or track_id == "" for track_id in track_ids
        ):
            return _error("INVALID_TRACK", "track_ids must be a non-empty array of non-empty strings.")
        resolved_ids: list[str] = []
        for track_id in track_ids:
            if track_id not in tracks_by_id:
                return _error("INVALID_TRACK", f"Track does not exist: {track_id}", track_id=track_id)
            if track_type is not None and tracks_by_id[track_id].type != track_type:
                return _error("INVALID_TRACK", f"Track does not match track_type: {track_id}", track_id=track_id)
            resolved_ids.append(track_id)
        return resolved_ids
    resolved_ids = [track.id for track in document.tracks if track_type is None or track.type == track_type]
    if len(resolved_ids) == 0:
        return _error("INVALID_TRACK", f"No {track_type} tracks are available for the edit.")
    return resolved_ids


def _insert_document_gap(
    document: TimelineDocument,
    position: float,
    duration: float,
    track_ids: list[str] | None,
    track_type: str | None,
    move_markers: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    position_value = _coerce_finite_float(position, "position")
    if isinstance(position_value, dict):
        return position_value
    position = position_value
    duration_value = _coerce_finite_float(duration, "duration")
    if isinstance(duration_value, dict):
        return duration_value
    duration = duration_value
    if position < 0:
        return _error("INVALID_TIMECODE", "position must be zero or greater.")
    if duration <= 0:
        return _error("INVALID_TIMECODE", "duration must be greater than zero.")
    selected_track_ids = _gap_track_ids(document, track_ids, track_type)
    if isinstance(selected_track_ids, dict):
        return selected_track_ids
    selected = set(selected_track_ids)

    for clip in document.clips:
        if clip.track_id in selected and clip.timeline_in < position < clip.timeline_out:
            return _error(
                "GAP_INTERSECTS_CLIP",
                "insert_timeline_gap cannot insert inside a clip. Split the clip first.",
                clip_id=clip.id,
                track_id=clip.track_id,
                position=position,
            )

    edited = document.model_copy(deep=True)
    shifted_clip_ids: list[str] = []
    shifted_marker_ids: list[str] = []
    for clip in edited.clips:
        if clip.track_id in selected and clip.timeline_in >= position:
            clip.timeline_in = round(clip.timeline_in + duration, 6)
            clip.timeline_out = round(clip.timeline_out + duration, 6)
            shifted_clip_ids.append(clip.id)
    if move_markers:
        for marker in edited.markers:
            if marker.position >= position:
                marker.position = round(marker.position + duration, 6)
                shifted_marker_ids.append(marker.id)

    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    before = {
        "position": position,
        "duration": duration,
        "track_ids": selected_track_ids,
        "summary": _timeline_summary(document),
    }
    after = {
        "position": position,
        "duration": duration,
        "track_ids": selected_track_ids,
        "shifted_clip_ids": sorted(shifted_clip_ids),
        "shifted_marker_ids": sorted(shifted_marker_ids),
        "summary": _timeline_summary(edited),
    }
    return edited, before, after


def _remove_document_gap(
    document: TimelineDocument,
    position: float,
    duration: float,
    track_ids: list[str] | None,
    track_type: str | None,
    move_markers: bool,
    remove_markers_in_gap: bool,
) -> tuple[TimelineDocument, dict[str, Any], dict[str, Any]] | dict[str, Any]:
    position_value = _coerce_finite_float(position, "position")
    if isinstance(position_value, dict):
        return position_value
    position = position_value
    duration_value = _coerce_finite_float(duration, "duration")
    if isinstance(duration_value, dict):
        return duration_value
    duration = duration_value
    if position < 0:
        return _error("INVALID_TIMECODE", "position must be zero or greater.")
    if duration <= 0:
        return _error("INVALID_TIMECODE", "duration must be greater than zero.")
    selected_track_ids = _gap_track_ids(document, track_ids, track_type)
    if isinstance(selected_track_ids, dict):
        return selected_track_ids
    selected = set(selected_track_ids)
    gap_end = round(position + duration, 6)

    for clip in document.clips:
        intersects_gap = clip.timeline_in < gap_end and clip.timeline_out > position
        if clip.track_id in selected and intersects_gap:
            return _error(
                "GAP_NOT_EMPTY",
                "remove_timeline_gap can only remove an empty timeline range.",
                clip_id=clip.id,
                track_id=clip.track_id,
                position=position,
                duration=duration,
            )

    edited = document.model_copy(deep=True)
    shifted_clip_ids: list[str] = []
    removed_marker_ids: list[str] = []
    shifted_marker_ids: list[str] = []
    for clip in edited.clips:
        if clip.track_id in selected and clip.timeline_in >= gap_end:
            clip.timeline_in = round(clip.timeline_in - duration, 6)
            clip.timeline_out = round(clip.timeline_out - duration, 6)
            shifted_clip_ids.append(clip.id)
    if move_markers:
        kept_markers: list[TimelineMarker] = []
        for marker in edited.markers:
            if position <= marker.position < gap_end and remove_markers_in_gap:
                removed_marker_ids.append(marker.id)
                continue
            if marker.position >= gap_end:
                marker.position = round(marker.position - duration, 6)
                shifted_marker_ids.append(marker.id)
            kept_markers.append(marker)
        edited.markers = kept_markers

    try:
        edited = TimelineDocument.model_validate(edited.model_dump(mode="json", exclude_none=True))
    except ValidationError as exc:
        return _error("INVALID_TIMELINE", f"Edited timeline is invalid: {exc}")
    before = {
        "position": position,
        "duration": duration,
        "gap_end": gap_end,
        "track_ids": selected_track_ids,
        "summary": _timeline_summary(document),
    }
    after = {
        "position": position,
        "duration": duration,
        "gap_end": gap_end,
        "track_ids": selected_track_ids,
        "shifted_clip_ids": sorted(shifted_clip_ids),
        "shifted_marker_ids": sorted(shifted_marker_ids),
        "removed_marker_ids": sorted(removed_marker_ids),
        "summary": _timeline_summary(edited),
    }
    return edited, before, after


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
    if isinstance(data, dict) and data.get("schema_version") != SUPPORTED_TIMELINE_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"Timeline schema_version {data.get('schema_version')!r} is not supported; "
            f"supported version is {SUPPORTED_TIMELINE_SCHEMA_VERSION}."
        )
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
    except UnsupportedSchemaVersion as exc:
        return _error("UNSUPPORTED_SCHEMA_VERSION", str(exc))
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


def trim_timeline_clip(
    timeline_file: str,
    clip_id: str,
    source_in: float | None = None,
    source_out: float | None = None,
    output_directory: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    include_linked: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _trim_document_clip(document, clip_id, source_in, source_out, include_linked)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="trim_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def move_timeline_clip(
    timeline_file: str,
    clip_id: str,
    timeline_in: float,
    output_directory: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    include_linked: bool = True,
    move_markers: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _move_document_clip(document, clip_id, timeline_in, include_linked, move_markers)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="move_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def split_timeline_clip(
    timeline_file: str,
    clip_id: str,
    split_at: float,
    output_directory: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    include_linked: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _split_document_clip(document, clip_id, split_at, include_linked)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="split_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def create_timeline_track(
    timeline_file: str,
    track_type: str,
    name: str | None = None,
    track_id: str | None = None,
    position: int | None = None,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _create_document_track(document, track_type, name, track_id, position)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="create_timeline_track",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def update_timeline_track(
    timeline_file: str,
    track_id: str,
    name: str | None = None,
    locked: bool | None = None,
    muted: bool | None = None,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    if name is None and locked is None and muted is None:
        return _error("INVALID_ARGUMENT", "name, locked, or muted is required.")
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _update_document_track(document, track_id, name, locked, muted)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="update_timeline_track",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def remove_timeline_track(
    timeline_file: str,
    track_id: str,
    remove_clips: bool = False,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _remove_document_track(document, track_id, remove_clips)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="remove_timeline_track",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def add_timeline_clip(
    timeline_file: str,
    track_id: str,
    media: str,
    source_in: float,
    source_out: float,
    timeline_in: float,
    media_id: str | None = None,
    clip_id: str | None = None,
    speed: float = 1.0,
    create_linked_clip: bool = False,
    linked_track_id: str | None = None,
    source_segment_id: str | None = None,
    reason: str | None = None,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = True,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _add_document_clip(
        document=document,
        track_id=track_id,
        media=media,
        source_in=float(source_in),
        source_out=float(source_out),
        timeline_in=float(timeline_in),
        media_id=media_id,
        clip_id=clip_id,
        speed=float(speed),
        create_linked_clip=create_linked_clip,
        linked_track_id=linked_track_id,
        source_segment_id=source_segment_id,
        reason=reason,
        require_media_exists=check_media_exists,
    )
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="add_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def remove_timeline_clip(
    timeline_file: str,
    clip_id: str,
    include_linked: bool = True,
    remove_markers: bool = False,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _remove_document_clip(document, clip_id, include_linked, remove_markers)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="remove_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def duplicate_timeline_clip(
    timeline_file: str,
    clip_id: str,
    timeline_in: float | None = None,
    new_clip_id: str | None = None,
    include_linked: bool = True,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _duplicate_document_clip(document, clip_id, timeline_in, new_clip_id, include_linked)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="duplicate_timeline_clip",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def insert_timeline_gap(
    timeline_file: str,
    position: float,
    duration: float,
    track_ids: list[str] | None = None,
    track_type: str | None = None,
    move_markers: bool = True,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _insert_document_gap(document, position, duration, track_ids, track_type, move_markers)
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="insert_timeline_gap",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def remove_timeline_gap(
    timeline_file: str,
    position: float,
    duration: float,
    track_ids: list[str] | None = None,
    track_type: str | None = None,
    move_markers: bool = True,
    remove_markers_in_gap: bool = True,
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, document = loaded
    edited_result = _remove_document_gap(
        document,
        position,
        duration,
        track_ids,
        track_type,
        move_markers,
        remove_markers_in_gap,
    )
    if isinstance(edited_result, dict):
        return edited_result
    edited, before, after = edited_result
    return _maybe_write_edited_timeline(
        operation="remove_timeline_gap",
        source_path=timeline_path,
        document=edited,
        output_directory=output_directory,
        name=output_name,
        overwrite=overwrite,
        dry_run=dry_run,
        before=before,
        after=after,
        check_media_exists=check_media_exists,
    )


def apply_timeline_edits(
    timeline_file: str,
    edits: list[dict[str, Any]],
    output_directory: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
    check_media_exists: bool = False,
) -> dict[str, Any]:
    if not isinstance(edits, list) or len(edits) == 0:
        return _error("INVALID_ARGUMENT", "edits must be a non-empty array.")
    loaded = _load_timeline_from_allowed_output(timeline_file)
    if isinstance(loaded, dict):
        return loaded
    timeline_path, original = loaded
    document = original.model_copy(deep=True)
    steps: list[dict[str, Any]] = []

    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict):
            return _error("INVALID_ARGUMENT", "Each edit must be an object.", failed_step=index, steps=steps)
        operation = str(edit.get("operation") or edit.get("type") or "")
        if operation in {"insert_timeline_gap", "timeline_insert_gap"}:
            operation = "insert_gap"
        elif operation in {"remove_timeline_gap", "timeline_remove_gap"}:
            operation = "remove_gap"
        else:
            operation = operation.removeprefix("timeline_").removesuffix("_timeline_clip")
            operation = operation.removesuffix("_clip")
        clip_id = edit.get("clip_id")
        clipless_operations = {"add", "insert_gap", "remove_gap"}
        if operation not in clipless_operations and (not isinstance(clip_id, str) or clip_id == ""):
            return _error("INVALID_CLIP", "Each edit requires a non-empty clip_id.", failed_step=index, steps=steps)

        if operation == "add":
            for required_field in ("track_id", "media", "source_in", "source_out", "timeline_in"):
                if required_field not in edit:
                    return _error(
                        "INVALID_ARGUMENT",
                        f"add edit requires {required_field}.",
                        failed_step=index,
                        steps=steps,
                    )
            edited_result = _add_document_clip(
                document=document,
                track_id=str(edit["track_id"]),
                media=str(edit["media"]),
                source_in=float(edit["source_in"]),
                source_out=float(edit["source_out"]),
                timeline_in=float(edit["timeline_in"]),
                media_id=edit.get("media_id"),
                clip_id=clip_id if isinstance(clip_id, str) and clip_id else None,
                speed=float(edit.get("speed", 1.0)),
                create_linked_clip=bool(edit.get("create_linked_clip", False)),
                linked_track_id=edit.get("linked_track_id"),
                source_segment_id=edit.get("source_segment_id"),
                reason=edit.get("reason"),
                require_media_exists=check_media_exists,
            )
            step_clip_id = clip_id or str(edit.get("track_id"))
        elif operation == "duplicate":
            edited_result = _duplicate_document_clip(
                document=document,
                clip_id=clip_id,
                timeline_in=edit.get("timeline_in"),
                new_clip_id=edit.get("new_clip_id"),
                include_linked=bool(edit.get("include_linked", True)),
            )
            step_clip_id = clip_id
        elif operation == "remove":
            edited_result = _remove_document_clip(
                document=document,
                clip_id=clip_id,
                include_linked=bool(edit.get("include_linked", True)),
                remove_markers=bool(edit.get("remove_markers", False)),
            )
            step_clip_id = clip_id
        elif operation == "trim":
            edited_result = _trim_document_clip(
                document=document,
                clip_id=clip_id,
                source_in=edit.get("source_in"),
                source_out=edit.get("source_out"),
                include_linked=bool(edit.get("include_linked", True)),
            )
            step_clip_id = clip_id
        elif operation == "move":
            if "timeline_in" not in edit:
                return _error("INVALID_TIMECODE", "move edit requires timeline_in.", failed_step=index, steps=steps)
            edited_result = _move_document_clip(
                document=document,
                clip_id=clip_id,
                timeline_in=float(edit["timeline_in"]),
                include_linked=bool(edit.get("include_linked", True)),
                move_markers=bool(edit.get("move_markers", True)),
            )
            step_clip_id = clip_id
        elif operation == "split":
            if "split_at" not in edit:
                return _error("INVALID_TIMECODE", "split edit requires split_at.", failed_step=index, steps=steps)
            edited_result = _split_document_clip(
                document=document,
                clip_id=clip_id,
                split_at=float(edit["split_at"]),
                include_linked=bool(edit.get("include_linked", True)),
            )
            step_clip_id = clip_id
        elif operation == "insert_gap":
            for required_field in ("position", "duration"):
                if required_field not in edit:
                    return _error(
                        "INVALID_ARGUMENT",
                        f"insert_gap edit requires {required_field}.",
                        failed_step=index,
                        steps=steps,
                    )
            position_value = _coerce_finite_float(edit["position"], "position")
            if isinstance(position_value, dict):
                return {
                    **position_value,
                    "failed_step": index,
                    "failed_edit": edit,
                    "steps": steps,
                }
            duration_value = _coerce_finite_float(edit["duration"], "duration")
            if isinstance(duration_value, dict):
                return {
                    **duration_value,
                    "failed_step": index,
                    "failed_edit": edit,
                    "steps": steps,
                }
            edited_result = _insert_document_gap(
                document=document,
                position=position_value,
                duration=duration_value,
                track_ids=edit.get("track_ids"),
                track_type=edit.get("track_type"),
                move_markers=bool(edit.get("move_markers", True)),
            )
            step_clip_id = None
        elif operation == "remove_gap":
            for required_field in ("position", "duration"):
                if required_field not in edit:
                    return _error(
                        "INVALID_ARGUMENT",
                        f"remove_gap edit requires {required_field}.",
                        failed_step=index,
                        steps=steps,
                    )
            position_value = _coerce_finite_float(edit["position"], "position")
            if isinstance(position_value, dict):
                return {
                    **position_value,
                    "failed_step": index,
                    "failed_edit": edit,
                    "steps": steps,
                }
            duration_value = _coerce_finite_float(edit["duration"], "duration")
            if isinstance(duration_value, dict):
                return {
                    **duration_value,
                    "failed_step": index,
                    "failed_edit": edit,
                    "steps": steps,
                }
            edited_result = _remove_document_gap(
                document=document,
                position=position_value,
                duration=duration_value,
                track_ids=edit.get("track_ids"),
                track_type=edit.get("track_type"),
                move_markers=bool(edit.get("move_markers", True)),
                remove_markers_in_gap=bool(edit.get("remove_markers_in_gap", True)),
            )
            step_clip_id = None
        else:
            return _error(
                "INVALID_ARGUMENT",
                f"Unsupported timeline edit operation: {operation}",
                failed_step=index,
                supported_operations=["add", "duplicate", "remove", "trim", "move", "split", "insert_gap", "remove_gap"],
                steps=steps,
            )

        if isinstance(edited_result, dict):
            return {
                **edited_result,
                "failed_step": index,
                "failed_edit": edit,
                "steps": steps,
            }
        document, before, after = edited_result
        steps.append(
            {
                "index": index,
                "operation": operation,
                "clip_id": step_clip_id,
                "before": before,
                "after": after,
            }
        )

    result = _maybe_write_edited_timeline(
        operation="apply_timeline_edits",
        source_path=timeline_path,
        document=document,
        output_directory=output_directory,
        name=name,
        overwrite=overwrite,
        dry_run=dry_run,
        before={"summary": _timeline_summary(original)},
        after={"summary": _timeline_summary(document)},
        check_media_exists=check_media_exists,
    )
    result["edit_count"] = len(edits)
    result["steps"] = steps
    return result


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
    except UnsupportedSchemaVersion as exc:
        return _error("UNSUPPORTED_SCHEMA_VERSION", str(exc))
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
    except UnsupportedSchemaVersion as exc:
        return _error("UNSUPPORTED_SCHEMA_VERSION", str(exc))
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


def apply_timeline_to_working_project(
    working_project: str,
    timeline_file: str,
    output_directory: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    check_mlt: bool = False,
) -> dict[str, Any]:
    try:
        working_path = ensure_project_path(working_project)
    except SecurityError as exc:
        return _security_error(exc)
    if not working_path.exists():
        return _error("PROJECT_NOT_FOUND", f"Working project does not exist: {working_path}")

    try:
        KdenliveProjectAdapter().inspect(working_path)
    except KdenliveProjectError as exc:
        return _error(exc.code, exc.message)

    try:
        output_dir = ensure_project_path(output_directory or str(working_path.parent))
    except SecurityError as exc:
        return _security_error(exc)

    derived_name = name or f"{working_path.stem}_edited"
    exported = export_timeline_to_kdenlive_template(
        timeline_file=timeline_file,
        template_project=str(working_path),
        output_directory=str(output_dir),
        name=derived_name,
        overwrite=overwrite,
        check_media_exists=True,
    )
    if not exported.get("success"):
        return exported

    result: dict[str, Any] = {
        "success": True,
        "operation": "apply_timeline_to_working_project",
        "working_project": str(working_path),
        "output_project": exported["project"],
        "inspection_summary": exported.get("inspection_summary", {}),
        "warnings": exported.get("warnings", []),
        "format": exported.get("format"),
        "kdenlive_project": exported.get("kdenlive_project"),
    }
    if check_mlt:
        from kdenlive_mcp.tools.project_tools import validate_project

        mlt = validate_project(exported["project"], check_mlt=True)
        mlt_load = mlt.get("checks", {}).get("mlt_load", {})
        result["mlt_load"] = mlt_load
        if not mlt.get("success"):
            return {
                **mlt,
                "operation": "apply_timeline_to_working_project",
                "working_project": str(working_path),
                "output_project": exported["project"],
                "warnings": [],
            }
        if mlt_load.get("valid") is False:
            return {
                "success": False,
                "operation": "apply_timeline_to_working_project",
                "error": "MLT_ERROR",
                "message": "Generated Kdenlive project failed MLT load validation.",
                "working_project": str(working_path),
                "output_project": exported["project"],
                "mlt_load": mlt_load,
                "warnings": [],
            }
        if mlt_load.get("valid") is None:
            result["warnings"] = result.get("warnings", []) + [
                {
                    "code": mlt_load.get("error", "MLT_VALIDATION_UNAVAILABLE"),
                    "message": "MLT load validation was requested but could not run in this environment.",
                }
            ]
    return result
