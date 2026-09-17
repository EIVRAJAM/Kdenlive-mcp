from __future__ import annotations

import json
import hashlib
import math
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument, TimelineEffect, TimelineTrack, VolumeKeyframe


TIMECODE_RE = re.compile(
    r"^(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?P<sep>[.:])(?P<fraction>\d{2,3})$"
)


class KdenliveProjectError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def element_properties(element: ET.Element) -> dict[str, str]:
    return {
        prop.attrib["name"]: prop.text or ""
        for prop in element.findall("property")
        if "name" in prop.attrib
    }


def _classify_audio_fade(track_kind: str, props: dict[str, str]) -> tuple[bool, dict[str, Any] | None]:
    if track_kind != "audio":
        return False, None
    if props.get("mlt_service") != "volume":
        return False, None
    kind = props.get("kdenlive_id")
    if kind not in ("fadein", "fadeout"):
        return False, None
    if "level" in props:
        return False, None
    window = props.get("window")
    try:
        window_ms = int(window) if window is not None else None
    except (TypeError, ValueError):
        window_ms = None
    if window_ms is None or window_ms <= 0:
        return False, None
    expected = ("0", "1") if kind == "fadein" else ("1", "0")
    if (props.get("gain"), props.get("end")) != expected:
        return False, None
    return True, {"kind": kind, "window_ms": window_ms, "gain": props.get("gain"), "end": props.get("end")}


def _parse_level(level: str, fps_num: int, fps_den: int) -> list[tuple[float, float]] | None:
    points: list[tuple[float, float]] = []
    for segment in level.split(";"):
        if not segment:
            return None
        if "=" not in segment:
            return None
        timecode, value = segment.split("=", 1)
        frame = parse_timecode_to_frames(timecode, fps_num, fps_den)
        if frame is None or frame < 0:
            return None
        try:
            parsed_value = float(value)
        except ValueError:
            return None
        points.append((round(frame * fps_den / fps_num, 6), parsed_value))
    return points


def _classify_volume_keyframes(
    track_kind: str,
    props: dict[str, str],
    fps_num: int,
    fps_den: int,
    source_duration: float | None,
) -> list[dict[str, float]] | None:
    if track_kind != "audio":
        return None
    if props.get("mlt_service") != "volume":
        return None
    if props.get("kdenlive_id") != "volume":
        return None
    level = props.get("level")
    if not level:
        return None
    raw = _parse_level(level, fps_num, fps_den)
    if raw is None:
        return None
    if len(raw) < 2:
        return None
    times = [point[0] for point in raw]
    if any(next_ <= current for current, next_ in zip(times, times[1:])):
        return None
    values = [point[1] for point in raw]
    if any(not math.isfinite(value) for value in values):
        return None
    if any(abs(round(value) - value) > 1e-6 for value in values):
        return None
    if any(value < 0 or value > 100 for value in values):
        return None
    if source_duration is not None:
        tolerance = 1 / fps_num * fps_den
        if any(time > source_duration + tolerance for time in times):
            return None
    return [
        {"position_s": round(time, 6), "value": round(value / 100.0, 6)}
        for time, value in raw
    ]


def parse_timecode_to_frames(value: str | None, fps_num: int, fps_den: int = 1) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    match = TIMECODE_RE.match(value)
    if not match:
        raise KdenliveProjectError("INVALID_TIMECODE", f"Unsupported timecode: {value}")

    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    fraction = int(match.group("fraction"))
    sep = match.group("sep")
    total_seconds = hours * 3600 + minutes * 60 + seconds

    if sep == ":" and len(match.group("fraction")) == 2:
        return int(round(total_seconds * fps_num / fps_den)) + fraction

    milliseconds = fraction if len(match.group("fraction")) == 3 else fraction * 10
    return int(round((total_seconds + milliseconds / 1000) * fps_num / fps_den))


def frame_to_kdenlive_timecode(frame: int, fps_num: int, fps_den: int = 1) -> str:
    if frame < 0:
        raise KdenliveProjectError("INVALID_TIMECODE", "Frame must be non-negative")
    total_seconds = frame * fps_den / fps_num
    milliseconds = int(round(total_seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def seconds_to_kdenlive_out_timecode(seconds: float, fps_num: int, fps_den: int = 1) -> str:
    if seconds <= 0:
        return frame_to_kdenlive_timecode(0, fps_num, fps_den)
    frame = max(0, int(round(seconds * fps_num / fps_den)) - 1)
    return frame_to_kdenlive_timecode(frame, fps_num, fps_den)


def seconds_to_kdenlive_in_timecode(seconds: float, fps_num: int, fps_den: int = 1) -> str:
    if seconds < 0:
        raise KdenliveProjectError("INVALID_TIMECODE", "Seconds must be non-negative")
    frame = int(round(seconds * fps_num / fps_den))
    return frame_to_kdenlive_timecode(frame, fps_num, fps_den)


def _set_property(element: ET.Element, name: str, value: str | int | float) -> None:
    for prop in element.findall("property"):
        if prop.attrib.get("name") == name:
            prop.text = str(value)
            return
    prop = ET.SubElement(element, "property", {"name": name})
    prop.text = str(value)


def _remove_children(parent: ET.Element, tags: set[str]) -> None:
    for child in list(parent):
        if child.tag in tags:
            parent.remove(child)


def _timeline_markers_json(timeline: TimelineDocument, fps_num: int, fps_den: int) -> str:
    markers = [
        {
            "comment": marker.comment,
            "duration": max(0, int(round(marker.duration * fps_num / fps_den))),
            "pos": max(0, int(round(marker.position * fps_num / fps_den))),
            "type": marker.type,
        }
        for marker in sorted(timeline.markers, key=lambda item: (item.position, item.id))
    ]
    return json.dumps(markers, indent=4)


def _chain_element(
    chain_id: str,
    resource: str,
    media_id: str,
    media_duration: float,
    fps_num: int,
    fps_den: int,
    *,
    set_audio: bool,
    set_image: bool,
    control_uuid: str | None = None,
) -> ET.Element:
    out = seconds_to_kdenlive_out_timecode(media_duration, fps_num, fps_den)
    length = max(1, int(round(media_duration * fps_num / fps_den)))
    chain = ET.Element("chain", {"id": chain_id, "out": out})
    for name, value in [
        ("length", length),
        ("eof", "pause"),
        ("resource", resource),
        ("mlt_service", "avformat-novalidate"),
        ("seekable", "1"),
        ("format", "3"),
        ("audio_index", "1"),
        ("video_index", "0"),
        ("vstream", "0"),
        ("astream", "0"),
        ("kdenlive:folderid", "-1"),
        ("kdenlive:id", media_id),
        ("kdenlive:control_uuid", control_uuid or "{" + str(uuid.uuid4()) + "}"),
        ("mute_on_pause", "0"),
        ("kdenlive:clip_type", "0"),
        ("set.test_audio", "1" if set_audio else "0"),
        ("set.test_image", "1" if set_image else "0"),
    ]:
        _set_property(chain, name, value)
    return chain


class KdenliveProjectAdapter:
    def inspect(self, project_path: str | Path) -> dict[str, Any]:
        path = Path(project_path)
        if not path.exists():
            raise KdenliveProjectError("PROJECT_NOT_FOUND", f"Project does not exist: {path}")
        if path.suffix != ".kdenlive":
            raise KdenliveProjectError("INVALID_PROJECT", f"Expected a .kdenlive file: {path}")

        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise KdenliveProjectError("INVALID_PROJECT", f"Project XML is invalid: {exc}") from exc

        if root.tag != "mlt":
            raise KdenliveProjectError("INVALID_PROJECT", f"Unexpected root element: {root.tag}")

        profile = self._profile(root)
        fps_num = profile["frame_rate_num"]
        fps_den = profile["frame_rate_den"]
        producers = {element.attrib["id"]: element for element in root.findall("producer") if "id" in element.attrib}
        chains = {element.attrib["id"]: element for element in root.findall("chain") if "id" in element.attrib}
        playlists = {element.attrib["id"]: element for element in root.findall("playlist") if "id" in element.attrib}
        tractors = {element.attrib["id"]: element for element in root.findall("tractor") if "id" in element.attrib}

        main_bin = playlists.get("main_bin")
        if main_bin is None:
            raise KdenliveProjectError("INVALID_PROJECT", "Project is missing playlist id='main_bin'")

        main_bin_props = element_properties(main_bin)
        sequence_ids = self._sequence_ids(main_bin, tractors)
        sequences = [
            self._sequence_summary(
                tractor_id=tractor_id,
                tractor=tractors[tractor_id],
                producers=producers,
                chains=chains,
                playlists=playlists,
                tractors=tractors,
                fps_num=fps_num,
                fps_den=fps_den,
            )
            for tractor_id in sequence_ids
            if tractor_id in tractors
        ]
        active_uuid = main_bin_props.get("kdenlive:docproperties.activetimeline")
        active_sequence = self._active_sequence_id(sequences, active_uuid)
        media = self._bin_media(main_bin, chains, root, path)
        missing_media = [item for item in media if item["resource_exists"] is False]

        return {
            "project": str(path),
            "root": {
                "tag": root.tag,
                "attributes": dict(root.attrib),
            },
            "profile": profile,
            "document": self._document_summary(main_bin_props),
            "bin": {
                "sequence_count": len(sequence_ids),
                "media_count": len(media),
                "media": media,
            },
            "sequences": sequences,
            "active_sequence_id": active_sequence,
            "validation": {
                "well_formed_xml": True,
                "missing_media_count": len(missing_media),
                "missing_media": missing_media,
            },
        }

    def extract_timeline_summary(self, project_path: str | Path) -> dict[str, Any]:
        path = Path(project_path)
        if not path.exists():
            raise KdenliveProjectError("PROJECT_NOT_FOUND", f"Project does not exist: {path}")
        if path.suffix != ".kdenlive":
            raise KdenliveProjectError("INVALID_PROJECT", f"Expected a .kdenlive file: {path}")
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise KdenliveProjectError("INVALID_PROJECT", f"Project XML is invalid: {exc}") from exc
        if root.tag != "mlt":
            raise KdenliveProjectError("INVALID_PROJECT", f"Unexpected root element: {root.tag}")

        profile = self._profile(root)
        fps_num = profile["frame_rate_num"]
        fps_den = profile["frame_rate_den"]
        fps = fps_num / fps_den if fps_den else None
        chains = {element.attrib["id"]: element for element in root.findall("chain") if "id" in element.attrib}
        playlists = {element.attrib["id"]: element for element in root.findall("playlist") if "id" in element.attrib}
        tractors = {element.attrib["id"]: element for element in root.findall("tractor") if "id" in element.attrib}
        main_bin = playlists.get("main_bin")
        sequence_tractor = self._active_sequence_tractor(main_bin, list(tractors.values()))
        sequence_id = sequence_tractor.attrib.get("id") if sequence_tractor is not None else None

        tracks: list[dict[str, Any]] = []
        clips: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        clip_effects: list[dict[str, Any]] = []

        if sequence_tractor is not None:
            for track in sequence_tractor.findall("track"):
                nested = tractors.get(track.attrib.get("producer") or "")
                if nested is None:
                    continue
                for branch in nested.findall("track"):
                    playlist = playlists.get(branch.attrib.get("producer") or "")
                    if playlist is None:
                        continue
                    track_kind = self._branch_kind(branch.attrib.get("hide"))
                    playlist_props = element_properties(playlist)
                    if playlist_props.get("kdenlive:audio_track") == "1":
                        track_kind = "audio"
                    track_summary, track_clips, track_gaps, track_effects = self._walk_playlist_summary(
                        playlist, branch.attrib.get("producer") or "", track_kind, chains, fps_num, fps_den
                    )
                    tracks.append(track_summary)
                    clips.extend(track_clips)
                    gaps.extend(track_gaps)
                    clip_effects.extend(track_effects)

        return {
            "project": str(path),
            "active_sequence_id": sequence_id,
            "fps": fps,
            "profile": {
                "width": profile.get("width"),
                "height": profile.get("height"),
                "frame_rate_num": fps_num,
                "frame_rate_den": fps_den,
            },
            "resolved_media": {
                item["media_id"]: item["resolved_path"]
                for item in self._bin_media(main_bin, chains, root, path)
                if item["media_id"] and item["resolved_path"]
            },
            "proxy_media_ids": self._proxy_media_ids(main_bin, chains),
            "tracks": tracks,
            "timeline_clips": clips,
            "gaps": gaps,
            "user_transitions": self._collect_user_transitions(root),
            "clip_effects": clip_effects,
            "confirmed_fields": [
                "active_sequence_id",
                "fps/profile",
                "source_in/source_out (entry attributes)",
                "media/resource (chain)",
                "duration_frames (out - in + 1)",
                "user transitions (in/out, no internal_added=237)",
                "clip effects (filter inside an entry, no internal_added=237)",
                "track_kind (hide / kdenlive:audio_track)",
            ],
            "inferred_fields": [
                "position_frames/seconds (accumulated entries + blanks, not stored by Kdenlive)",
                "track_kind when neither hide nor audio_track is decisive",
            ],
        }

    def extract_timeline_document(self, project_path: str | Path) -> TimelineDocument:
        summary = self.extract_timeline_summary(project_path)

        if any(transition.get("is_user") for transition in summary["user_transitions"]):
            raise KdenliveProjectError(
                "UNSUPPORTED_TIMELINE_FEATURE",
                "User transitions are not supported by reverse timeline conversion yet.",
            )
        if any(not effect.get("supported") for effect in summary["clip_effects"]):
            raise KdenliveProjectError(
                "UNSUPPORTED_TIMELINE_FEATURE",
                "Clip effects are not supported by reverse timeline conversion yet.",
            )
        if summary.get("proxy_media_ids"):
            raise KdenliveProjectError(
                "UNSUPPORTED_TIMELINE_FEATURE",
                "Proxy attachments are not supported by reverse timeline conversion yet.",
            )

        fps = summary["fps"] or 30.0
        profile = summary["profile"]
        width = int(profile.get("width") or 1080)
        height = int(profile.get("height") or 1920)

        kind_counters: dict[str, int] = {"video": 0, "audio": 0}
        tracks: list[TimelineTrack] = []
        track_by_playlist: dict[str, TimelineTrack] = {}
        for track in summary["tracks"]:
            playlist_id = track.get("id") or ""
            if (track.get("clip_count") or 0) == 0 and (track.get("gap_count") or 0) == 0:
                continue
            kind = track.get("track_kind")
            if kind not in ("video", "audio"):
                raise KdenliveProjectError(
                    "UNSUPPORTED_TIMELINE_FEATURE",
                    f"Track {playlist_id} has an unsupported track kind: {kind}",
                )
            kind_counters[kind] += 1
            number = kind_counters[kind]
            char = "v" if kind == "video" else "a"
            track_id = f"track_{char}{number}_{playlist_id}"
            name = f"{'Video' if kind == 'video' else 'Audio'} {number}"
            timeline_track = TimelineTrack(id=track_id, type=kind, name=name)
            tracks.append(timeline_track)
            track_by_playlist[playlist_id] = timeline_track

        clips: list[TimelineClip] = []
        used_ids: set[str] = set()
        for clip in summary["timeline_clips"]:
            media = clip.get("media")
            duration_frames = int(clip.get("duration_frames") or 0)
            if not media:
                continue
            if duration_frames <= 0:
                continue
            playlist_id = clip.get("playlist_id") or ""
            timeline_track = track_by_playlist.get(playlist_id)
            if timeline_track is None:
                raise KdenliveProjectError(
                    "UNSUPPORTED_TIMELINE_FEATURE",
                    f"Clip {clip.get('producer')} in playlist {playlist_id} has no convertible track.",
                )

            source_in_frames = int(clip.get("source_in_frames") or 0)
            source_out_frames = int(clip.get("source_out_frames") or 0)
            position_frames = int(clip.get("position_frames") or 0)

            source_in = source_in_frames / fps
            source_out = (source_out_frames + 1) / fps
            timeline_in = position_frames / fps
            timeline_out = timeline_in + (source_out - source_in)

            kind = timeline_track.type
            base_id = f"{clip.get('producer') or 'clip'}_{'v' if kind == 'video' else 'a'}"
            clip_id = base_id
            suffix = 1
            while clip_id in used_ids:
                clip_id = f"{base_id}_{suffix}"
                suffix += 1
            used_ids.add(clip_id)

            media_id = clip.get("media_id") or f"media_{hashlib.sha1(str(media).encode('utf-8')).hexdigest()[:12]}"
            resolved_media = summary.get("resolved_media") or {}
            media_path = resolved_media.get(clip.get("media_id") or "")
            if not media_path:
                raw = Path(str(media))
                media_path = str(raw if raw.is_absolute() else Path(project_path).resolve().parent / raw)

            effects: list[TimelineEffect] = []
            for fade in clip.get("supported_audio_fades") or []:
                effects.append(
                    TimelineEffect(id=f"{clip_id}_{fade['kind']}", kind=fade["kind"], window_ms=int(fade["window_ms"]))
                )
            volume_curves = clip.get("supported_volume_keyframes") or []
            if len(volume_curves) > 1:
                raise KdenliveProjectError(
                    "UNSUPPORTED_TIMELINE_FEATURE",
                    f"Clip {clip_id} has multiple volume keyframe curves.",
                )
            if volume_curves:
                effects.append(
                    TimelineEffect(
                        id=f"{clip_id}_volume_keyframes",
                        kind="volume_keyframes",
                        points=[VolumeKeyframe(**point) for point in volume_curves[0]["points"]],
                    )
                )
            fade_kinds = [effect.kind for effect in effects]
            if len(fade_kinds) != len(set(fade_kinds)):
                raise KdenliveProjectError(
                    "UNSUPPORTED_TIMELINE_FEATURE",
                    f"Clip {clip_id} has duplicate audio fades of the same kind.",
                )
            clips.append(
                TimelineClip(
                    id=clip_id,
                    track_id=timeline_track.id,
                    media_id=media_id,
                    media=str(media_path),
                    source_in=round(source_in, 6),
                    source_out=round(source_out, 6),
                    timeline_in=round(timeline_in, 6),
                    timeline_out=round(timeline_out, 6),
                    reason="reverse_converted",
                    effects=effects,
                )
            )

        self._link_audio_video_pairs(tracks, clips)

        return TimelineDocument(
            fps=float(fps),
            width=width,
            height=height,
            tracks=tracks,
            clips=clips,
        )

    def _link_audio_video_pairs(self, tracks: list[TimelineTrack], clips: list[TimelineClip]) -> None:
        track_by_id = {track.id: track for track in tracks}
        audio_clips = [clip for clip in clips if track_by_id[clip.track_id].type == "audio"]
        unlinked_audio = list(audio_clips)
        for video_clip in clips:
            if track_by_id[video_clip.track_id].type != "video" or video_clip.linked_clip_id:
                continue
            candidates = [
                audio_clip
                for audio_clip in unlinked_audio
                if audio_clip.linked_clip_id is None
                and (
                    (video_clip.media_id and audio_clip.media_id and video_clip.media_id == audio_clip.media_id)
                    or video_clip.media == audio_clip.media
                )
                and video_clip.source_in == audio_clip.source_in
                and video_clip.source_out == audio_clip.source_out
                and video_clip.timeline_in == audio_clip.timeline_in
                and video_clip.timeline_out == audio_clip.timeline_out
            ]
            if len(candidates) > 1:
                raise KdenliveProjectError(
                    "UNSUPPORTED_TIMELINE_FEATURE",
                    f"Ambiguous audio/video pairing for clip {video_clip.id}; reverse linking is not lossless.",
                )
            if len(candidates) == 1:
                audio_clip = candidates[0]
                video_clip.linked_clip_id = audio_clip.id
                audio_clip.linked_clip_id = video_clip.id

    def _walk_playlist_summary(
        self,
        playlist: ET.Element,
        playlist_id: str,
        track_kind: str,
        chains: dict[str, ET.Element],
        fps_num: int,
        fps_den: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        position_frames = 0
        clips: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        effects: list[dict[str, Any]] = []
        for child in playlist:
            if child.tag == "blank":
                length = self._blank_length_frames(child, fps_num, fps_den)
                if length > 0:
                    gaps.append(
                        {
                            "playlist_id": playlist_id,
                            "track_kind": track_kind,
                            "start_frames": position_frames,
                            "start_seconds": round(position_frames / fps_num * fps_den, 6),
                            "duration_frames": length,
                            "duration_seconds": round(length / fps_num * fps_den, 6),
                        }
                    )
                    position_frames += length
                continue
            if child.tag != "entry":
                continue
            producer = child.attrib.get("producer")
            chain = chains.get(producer or "")
            chain_props = element_properties(chain) if chain is not None else {}
            in_frames = parse_timecode_to_frames(child.attrib.get("in"), fps_num, fps_den)
            out_frames = parse_timecode_to_frames(child.attrib.get("out"), fps_num, fps_den)
            duration_frames = None
            if in_frames is not None and out_frames is not None:
                duration_frames = out_frames - in_frames + 1
            source_duration = None
            if in_frames is not None and out_frames is not None:
                source_duration = round((out_frames - in_frames) * fps_den / fps_num, 6)
            entry_effects: list[dict[str, Any]] = []
            supported_fades: list[dict[str, Any]] = []
            supported_volume_keyframes: list[dict[str, Any]] = []
            for filter_ in child.findall("filter"):
                filter_props = element_properties(filter_)
                if filter_props.get("mlt_service") and filter_props.get("internal_added") != "237":
                    supported, fade = _classify_audio_fade(track_kind, filter_props)
                    volume_points = None
                    if fade is None:
                        volume_points = _classify_volume_keyframes(
                            track_kind, filter_props, fps_num, fps_den, source_duration
                        )
                        if volume_points is not None:
                            supported_volume_keyframes.append(
                                {"filter_id": filter_.attrib.get("id"), "points": volume_points}
                            )
                    elif fade is not None:
                        fade["filter_id"] = filter_.attrib.get("id")
                        supported_fades.append(fade)
                    entry_effects.append(
                        {
                            "entry_producer": producer,
                            "filter_id": filter_.attrib.get("id"),
                            "mlt_service": filter_props.get("mlt_service"),
                            "kdenlive_id": filter_props.get("kdenlive_id"),
                            "track_kind": track_kind,
                            "supported": supported or volume_points is not None,
                        }
                    )
            effects.extend(entry_effects)
            clips.append(
                {
                    "producer": producer,
                    "playlist_id": playlist_id,
                    "track_kind": track_kind,
                    "media": chain_props.get("resource"),
                    "media_id": chain_props.get("kdenlive:id"),
                    "source_in": child.attrib.get("in"),
                    "source_out": child.attrib.get("out"),
                    "source_in_frames": in_frames,
                    "source_out_frames": out_frames,
                    "duration_frames": duration_frames,
                    "duration_seconds": round(duration_frames / fps_num * fps_den, 6) if duration_frames is not None else None,
                    "position_frames": position_frames,
                    "position_seconds": round(position_frames / fps_num * fps_den, 6),
                    "effect_count": len(entry_effects),
                    "supported_audio_fades": supported_fades,
                    "supported_volume_keyframes": supported_volume_keyframes,
                }
            )
            if duration_frames is not None:
                position_frames += duration_frames
        return (
            {"id": playlist_id, "track_kind": track_kind, "clip_count": len(clips), "gap_count": len(gaps)},
            clips,
            gaps,
            effects,
        )

    def _collect_user_transitions(self, root: ET.Element) -> list[dict[str, Any]]:
        transitions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for transition in root.iter("transition"):
            transition_id = transition.attrib.get("id")
            if transition_id and transition_id in seen:
                continue
            if transition_id:
                seen.add(transition_id)
            props = element_properties(transition)
            internal = props.get("internal_added")
            service = props.get("mlt_service")
            has_in_out = transition.attrib.get("in") is not None and transition.attrib.get("out") is not None
            is_user = internal != "237" and (has_in_out or service not in {"mix", "qtblend"})
            transitions.append(
                {
                    "id": transition_id,
                    "mlt_service": service,
                    "kdenlive_id": props.get("kdenlive_id"),
                    "in": transition.attrib.get("in"),
                    "out": transition.attrib.get("out"),
                    "internal_added": internal,
                    "is_user": is_user,
                }
            )
        return transitions

    def _profile(self, root: ET.Element) -> dict[str, Any]:
        profile = root.find("profile")
        if profile is None:
            raise KdenliveProjectError("INVALID_PROJECT", "Project is missing profile")
        attrs = dict(profile.attrib)
        return {
            **attrs,
            "width": int(attrs["width"]),
            "height": int(attrs["height"]),
            "frame_rate_num": int(attrs["frame_rate_num"]),
            "frame_rate_den": int(attrs["frame_rate_den"]),
            "display_aspect_num": int(attrs["display_aspect_num"]),
            "display_aspect_den": int(attrs["display_aspect_den"]),
        }

    def _document_summary(self, props: dict[str, str]) -> dict[str, Any]:
        prefix = "kdenlive:docproperties."
        doc_props = {key.removeprefix(prefix): value for key, value in props.items() if key.startswith(prefix)}
        return {
            "kdenlive_version": doc_props.get("kdenliveversion"),
            "format_version": doc_props.get("version"),
            "profile": doc_props.get("profile"),
            "document_id": doc_props.get("documentid"),
            "storage_folder": doc_props.get("storagefolder"),
            "uuid": doc_props.get("uuid"),
            "active_timeline": doc_props.get("activetimeline"),
            "open_sequences": doc_props.get("opensequences"),
            "proxy_enabled": doc_props.get("enableproxy") == "1",
            "generate_proxy": doc_props.get("generateproxy") == "1",
            "properties": doc_props,
        }

    def _sequence_ids(self, main_bin: ET.Element, tractors: dict[str, ET.Element]) -> list[str]:
        ids: list[str] = []
        for entry in main_bin.findall("entry"):
            producer = entry.attrib.get("producer")
            if producer in tractors:
                props = element_properties(tractors[producer])
                if props.get("kdenlive:producer_type") == "17" or props.get("kdenlive:clipname"):
                    ids.append(producer)
        return ids

    def _active_sequence_id(self, sequences: list[dict[str, Any]], active_uuid: str | None) -> str | None:
        if active_uuid:
            for sequence in sequences:
                if sequence.get("uuid") == active_uuid:
                    return sequence["id"]
        return sequences[0]["id"] if sequences else None

    def _proxy_media_ids(self, main_bin: ET.Element, chains: dict[str, ET.Element]) -> list[str]:
        proxy_ids: set[str] = set()
        for entry in main_bin.findall("entry"):
            producer = entry.attrib.get("producer")
            chain = chains.get(producer or "")
            if chain is None:
                continue
            props = element_properties(chain)
            if props.get("kdenlive:proxy") or props.get("kdenlive:proxy_metadata"):
                media_id = props.get("kdenlive:id")
                if media_id:
                    proxy_ids.add(media_id)
        return sorted(proxy_ids)

    def _bin_media(
        self,
        main_bin: ET.Element,
        chains: dict[str, ET.Element],
        root: ET.Element,
        project_path: Path,
    ) -> list[dict[str, Any]]:
        project_root = Path(root.attrib.get("root") or project_path.parent)
        media: list[dict[str, Any]] = []
        for entry in main_bin.findall("entry"):
            producer = entry.attrib.get("producer")
            if producer not in chains:
                continue
            chain = chains[producer]
            props = element_properties(chain)
            resource = props.get("resource")
            resolved = self._resolve_resource(project_root, resource)
            media.append(
                {
                    "xml_id": producer,
                    "media_id": props.get("kdenlive:id"),
                    "resource": resource,
                    "resolved_path": str(resolved) if resolved else None,
                    "resource_exists": resolved.exists() if resolved else None,
                    "folder_id": props.get("kdenlive:folderid"),
                    "clip_type": props.get("kdenlive:clip_type"),
                    "file_hash": props.get("kdenlive:file_hash"),
                    "file_size": self._int_or_none(props.get("kdenlive:file_size")),
                    "service": props.get("mlt_service"),
                    "in": entry.attrib.get("in"),
                    "out": entry.attrib.get("out"),
                }
            )
        return media

    def _sequence_summary(
        self,
        tractor_id: str,
        tractor: ET.Element,
        producers: dict[str, ET.Element],
        chains: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
        tractors: dict[str, ET.Element],
        fps_num: int,
        fps_den: int,
    ) -> dict[str, Any]:
        props = element_properties(tractor)
        tracks = self._sequence_tracks(tractor, producers, chains, playlists, tractors, fps_num, fps_den)
        timeline_clips = [clip for track in tracks for clip in track["clips"]]
        return {
            "id": tractor_id,
            "name": props.get("kdenlive:clipname"),
            "uuid": props.get("kdenlive:uuid"),
            "kdenlive_id": props.get("kdenlive:id"),
            "in": tractor.attrib.get("in"),
            "out": tractor.attrib.get("out"),
            "duration": props.get("kdenlive:duration"),
            "max_duration_frames": self._int_or_none(props.get("kdenlive:maxduration")),
            "position_frames": self._int_or_none(props.get("kdenlive:sequenceproperties.position")),
            "tracks_count": self._int_or_none(props.get("kdenlive:sequenceproperties.tracksCount")),
            "video_target": self._int_or_none(props.get("kdenlive:sequenceproperties.videoTarget")),
            "audio_target": self._int_or_none(props.get("kdenlive:sequenceproperties.audioTarget")),
            "tracks": tracks,
            "timeline_clip_count": len(timeline_clips),
            "timeline_clips": timeline_clips,
            "guides": self._json_property(props.get("kdenlive:sequenceproperties.guides"), default=[]),
            "markers": self._json_property(props.get("kdenlive:markers"), default=[]),
            "groups": self._json_property(props.get("kdenlive:sequenceproperties.groups"), default=[]),
        }

    def _sequence_tracks(
        self,
        sequence: ET.Element,
        producers: dict[str, ET.Element],
        chains: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
        tractors: dict[str, ET.Element],
        fps_num: int,
        fps_den: int,
    ) -> list[dict[str, Any]]:
        tracks: list[dict[str, Any]] = []
        track_elements = sequence.findall("track")
        for sequence_index, track_element in enumerate(track_elements):
            producer_id = track_element.attrib.get("producer")
            if producer_id in producers:
                tracks.append(
                    {
                        "sequence_index": sequence_index,
                        "id": producer_id,
                        "kind": "background",
                        "playlists": [],
                        "clips": [],
                    }
                )
                continue
            nested = tractors.get(producer_id or "")
            if nested is None:
                tracks.append(
                    {
                        "sequence_index": sequence_index,
                        "id": producer_id,
                        "kind": "unknown",
                        "playlists": [],
                        "clips": [],
                    }
                )
                continue
            tracks.extend(
                self._nested_track_summaries(
                    sequence_index,
                    producer_id or "",
                    nested,
                    chains,
                    playlists,
                    fps_num,
                    fps_den,
                )
            )
        return tracks

    def _nested_track_summaries(
        self,
        sequence_index: int,
        tractor_id: str,
        tractor: ET.Element,
        chains: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
        fps_num: int,
        fps_den: int,
    ) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for branch_index, branch in enumerate(tractor.findall("track")):
            playlist_id = branch.attrib.get("producer")
            playlist = playlists.get(playlist_id or "")
            kind = self._branch_kind(branch.attrib.get("hide"))
            clips = (
                self._playlist_clips(playlist, playlist_id or "", chains, fps_num, fps_den)
                if playlist is not None
                else []
            )
            summaries.append(
                {
                    "sequence_index": sequence_index,
                    "tractor_id": tractor_id,
                    "branch_index": branch_index,
                    "id": playlist_id,
                    "kind": kind,
                    "hidden": branch.attrib.get("hide"),
                    "clips": clips,
                    "clip_count": len(clips),
                }
            )
        return summaries

    def _playlist_clips(
        self,
        playlist: ET.Element,
        playlist_id: str,
        chains: dict[str, ET.Element],
        fps_num: int,
        fps_den: int,
    ) -> list[dict[str, Any]]:
        clips: list[dict[str, Any]] = []
        position = 0
        clip_index = 0
        for child in playlist:
            if child.tag == "blank":
                length = self._blank_length_frames(child, fps_num, fps_den)
                position += length
                continue
            if child.tag != "entry":
                continue
            in_frames = parse_timecode_to_frames(child.attrib.get("in"), fps_num, fps_den)
            out_frames = parse_timecode_to_frames(child.attrib.get("out"), fps_num, fps_den)
            duration = None
            if in_frames is not None and out_frames is not None:
                duration = out_frames - in_frames + 1
            producer_id = child.attrib.get("producer")
            chain = chains.get(producer_id or "")
            chain_props = element_properties(chain) if chain is not None else {}
            entry_props = element_properties(child)
            clips.append(
                {
                    "timeline_id": f"{playlist_id}:{position}:{producer_id}",
                    "playlist_id": playlist_id,
                    "playlist_index": clip_index,
                    "xml_producer": producer_id,
                    "media_id": entry_props.get("kdenlive:id") or chain_props.get("kdenlive:id"),
                    "resource": chain_props.get("resource"),
                    "start_frame": position,
                    "in": child.attrib.get("in"),
                    "out": child.attrib.get("out"),
                    "in_frame": in_frames,
                    "out_frame": out_frames,
                    "duration_frames": duration,
                }
            )
            if duration is not None:
                position += duration
            clip_index += 1
        return clips

    def _blank_length_frames(self, blank: ET.Element, fps_num: int, fps_den: int) -> int:
        length = blank.attrib.get("length")
        if length is None:
            return 0
        parsed = parse_timecode_to_frames(length, fps_num, fps_den)
        return parsed or 0

    def _branch_kind(self, hidden: str | None) -> str:
        if hidden == "video":
            return "audio"
        if hidden == "audio":
            return "video"
        return "unknown"

    def _json_property(self, value: str | None, default: Any) -> Any:
        if value is None or value.strip() == "":
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _resolve_resource(self, root: Path, resource: str | None) -> Path | None:
        if not resource or resource == "black":
            return None
        resource_path = Path(resource)
        if resource_path.is_absolute():
            return resource_path
        return root / resource_path

    def _int_or_none(self, value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def write_timeline_from_template(
        self,
        template_project: str | Path,
        output_project: str | Path,
        timeline: TimelineDocument,
    ) -> dict[str, Any]:
        template_path = Path(template_project)
        output_path = Path(output_project)
        try:
            tree = ET.parse(template_path)
        except ET.ParseError as exc:
            raise KdenliveProjectError("INVALID_PROJECT", f"Template XML is invalid: {exc}") from exc

        root = tree.getroot()
        if root.tag != "mlt":
            raise KdenliveProjectError("INVALID_PROJECT", f"Unexpected template root element: {root.tag}")
        profile = self._profile(root)
        fps_num = profile["frame_rate_num"]
        fps_den = profile["frame_rate_den"]
        root.attrib["root"] = str(output_path.parent)

        playlists = {element.attrib["id"]: element for element in root.findall("playlist") if "id" in element.attrib}
        tractors = {element.attrib["id"]: element for element in root.findall("tractor") if "id" in element.attrib}
        main_bin = playlists.get("main_bin")
        if main_bin is None:
            raise KdenliveProjectError("INVALID_PROJECT", "Template is missing required main_bin playlist")

        sequence_tractor = self._active_sequence_tractor(main_bin, list(tractors.values()))
        timeline_playlist_map = self._timeline_playlist_map(sequence_tractor, tractors, playlists, timeline)
        if not timeline_playlist_map:
            raise KdenliveProjectError("INVALID_PROJECT", "Template is missing editable audio/video target playlists")

        for chain in root.findall("chain"):
            root.remove(chain)
        for playlist in self._candidate_timeline_playlists(sequence_tractor, tractors, playlists)[0]:
            _remove_children(playlist, {"entry", "blank"})
        for playlist in self._candidate_timeline_playlists(sequence_tractor, tractors, playlists)[1]:
            _remove_children(playlist, {"entry", "blank"})
        for entry in list(main_bin.findall("entry")):
            producer = entry.attrib.get("producer")
            if producer and producer.startswith("chain"):
                main_bin.remove(entry)

        media_paths: dict[str, str] = {}
        media_durations: dict[str, float] = {}
        for clip in timeline.clips:
            media_paths.setdefault(clip.media_id, clip.media)
            media_durations[clip.media_id] = max(media_durations.get(clip.media_id, 0.0), clip.source_out)

        chain_insert_index = 1
        chain_counter = 0
        filter_counter = 0
        bin_chain_ids: dict[str, str] = {}
        timeline_chain_ids: dict[str, str] = {}
        media_id_map = {media_id: str(index) for index, media_id in enumerate(sorted(media_paths), start=4)}

        def new_uuid() -> str:
            return "{" + str(uuid.uuid4()) + "}"

        def add_chain(media_id: str, *, set_audio: bool, set_image: bool, control_uuid: str) -> str:
            nonlocal chain_counter, chain_insert_index
            chain_id = f"chain{chain_counter}"
            chain_counter += 1
            resource = media_paths[media_id]
            chain = _chain_element(
                chain_id=chain_id,
                resource=resource,
                media_id=media_id_map[media_id],
                media_duration=media_durations[media_id],
                fps_num=fps_num,
                fps_den=fps_den,
                set_audio=set_audio,
                set_image=set_image,
                control_uuid=control_uuid,
            )
            root.insert(chain_insert_index, chain)
            chain_insert_index += 1
            return chain_id

        for media_id in sorted(media_paths):
            control_uuid = new_uuid()
            bin_chain_ids[media_id] = add_chain(
                media_id, set_audio=False, set_image=True, control_uuid=control_uuid
            )
            timeline_chain_ids[media_id] = add_chain(
                media_id, set_audio=True, set_image=True, control_uuid=control_uuid
            )

        def append_clip_fade_filter(entry: ET.Element, effect: TimelineEffect) -> None:
            nonlocal filter_counter
            filter_el = ET.SubElement(entry, "filter", {"id": f"filter{filter_counter}"})
            filter_counter += 1
            _set_property(filter_el, "mlt_service", "volume")
            if effect.kind == "volume_keyframes":
                _set_property(filter_el, "kdenlive_id", "volume")
                _set_property(filter_el, "window", "75")
                _set_property(filter_el, "max_gain", "20dB")
                _set_property(filter_el, "channel_mask", "-1")
                level = ";".join(
                    f"{seconds_to_kdenlive_in_timecode(point.position_s, fps_num, fps_den)}={int(round(point.value * 100))}"
                    for point in effect.points
                )
                _set_property(filter_el, "level", level)
                _set_property(filter_el, "kdenlive:kfrhidden", "0")
                _set_property(filter_el, "kdenlive:collapsed", "0")
                return
            _set_property(filter_el, "window", str(effect.window_ms))
            _set_property(filter_el, "max_gain", "20dB")
            _set_property(filter_el, "channel_mask", "-1")
            _set_property(filter_el, "kdenlive_id", effect.kind)
            if effect.kind == "fadein":
                _set_property(filter_el, "gain", "0")
                _set_property(filter_el, "end", "1")
            else:
                _set_property(filter_el, "gain", "1")
                _set_property(filter_el, "end", "0")
            _set_property(filter_el, "kdenlive:collapsed", "0")

        def append_playlist_entry(playlist: ET.Element, clip: TimelineClip) -> None:
            entry = ET.SubElement(
                playlist,
                "entry",
                {
                    "in": seconds_to_kdenlive_in_timecode(clip.source_in, fps_num, fps_den),
                    "out": seconds_to_kdenlive_out_timecode(clip.source_out, fps_num, fps_den),
                    "producer": timeline_chain_ids[clip.media_id],
                },
            )
            _set_property(entry, "kdenlive:id", media_id_map[clip.media_id])
            _set_property(entry, "kdenlive:audio_index", "1")
            for effect in clip.effects:
                append_clip_fade_filter(entry, effect)

        def append_track_clips(playlist: ET.Element, track_id: str) -> None:
            cursor = 0.0
            for clip in sorted(
                [clip for clip in timeline.clips if clip.track_id == track_id],
                key=lambda item: (item.timeline_in, item.id),
            ):
                if clip.timeline_in > cursor:
                    blank_length = int(round((clip.timeline_in - cursor) * fps_num / fps_den))
                    if blank_length > 0:
                        ET.SubElement(
                            playlist,
                            "blank",
                            {"length": frame_to_kdenlive_timecode(blank_length, fps_num, fps_den)},
                        )
                append_playlist_entry(playlist, clip)
                cursor = max(cursor, clip.timeline_out)

        for track in timeline.tracks:
            playlist = timeline_playlist_map.get(track.id)
            if playlist is not None:
                append_track_clips(playlist, track.id)

        for media_id in sorted(media_paths):
            entry = ET.SubElement(
                main_bin,
                "entry",
                {
                    "in": "00:00:00.000",
                    "out": seconds_to_kdenlive_out_timecode(media_durations[media_id], fps_num, fps_den),
                    "producer": bin_chain_ids[media_id],
                },
            )
            _set_property(entry, "kdenlive:id", media_id_map[media_id])

        project_out = seconds_to_kdenlive_out_timecode(timeline.duration, fps_num, fps_den)
        for tractor_id in ("tractor0", "tractor3", "tractor4", "tractor5"):
            tractor = tractors.get(tractor_id)
            if tractor is not None:
                tractor.attrib["out"] = project_out
                _set_property(tractor, "kdenlive:duration", project_out)
                _set_property(tractor, "kdenlive:maxduration", max(1, int(round(timeline.duration * fps_num / fps_den))))

        project_tractor = tractors.get("tractor5")
        if project_tractor is not None:
            for track in project_tractor.findall("track"):
                if track.attrib.get("producer") == "tractor4":
                    track.set("in", "00:00:00.000")
                    track.set("out", project_out)
        for entry in main_bin.findall("entry"):
            if entry.attrib.get("producer") == "tractor4":
                entry.set("in", "00:00:00.000")
                entry.set("out", project_out)

        if sequence_tractor is not None:
            markers_json = _timeline_markers_json(timeline, fps_num, fps_den)
            _set_property(sequence_tractor, "kdenlive:sequenceproperties.guides", markers_json)
            _set_property(sequence_tractor, "kdenlive:markers", markers_json)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(tree, space=" ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return {
            "project": str(output_path),
            "template": str(template_path),
            "media_count": len(media_paths),
            "timeline_clip_count": len(timeline.clips),
            "marker_count": len(timeline.markers),
            "track_playlist_map": {
                track_id: playlist.attrib.get("id") for track_id, playlist in sorted(timeline_playlist_map.items())
            },
        }

    def _active_sequence_tractor(self, main_bin: ET.Element, tractors: list[ET.Element]) -> ET.Element | None:
        main_bin_props = element_properties(main_bin)
        active_uuid = main_bin_props.get("kdenlive:docproperties.activetimeline")
        for tractor in tractors:
            props = element_properties(tractor)
            if active_uuid and props.get("kdenlive:uuid") == active_uuid:
                return tractor
        for tractor in tractors:
            props = element_properties(tractor)
            if props.get("kdenlive:producer_type") == "17":
                return tractor
        return None

    def _target_timeline_playlists(
        self,
        sequence_tractor: ET.Element | None,
        tractors: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
    ) -> tuple[ET.Element | None, ET.Element | None]:
        audio_candidates, video_candidates = self._candidate_timeline_playlists(sequence_tractor, tractors, playlists)
        audio_playlist = audio_candidates[0] if audio_candidates else None
        # Kdenlive's captured vertical template orders video branches bottom-to-top;
        # the active V1 target is the first branch of the top editable video tractor.
        video_playlist = video_candidates[-2] if len(video_candidates) >= 2 else (video_candidates[0] if video_candidates else None)
        return audio_playlist, video_playlist

    def _candidate_timeline_playlists(
        self,
        sequence_tractor: ET.Element | None,
        tractors: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
    ) -> tuple[list[ET.Element], list[ET.Element]]:
        if sequence_tractor is None:
            return [], []

        audio_candidates: list[ET.Element] = []
        video_candidates: list[ET.Element] = []
        for track in sequence_tractor.findall("track"):
            nested = tractors.get(track.attrib.get("producer") or "")
            if nested is None:
                continue
            for branch in nested.findall("track"):
                playlist = playlists.get(branch.attrib.get("producer") or "")
                if playlist is None:
                    continue
                kind = self._branch_kind(branch.attrib.get("hide"))
                if kind == "audio":
                    audio_candidates.append(playlist)
                elif kind == "video":
                    video_candidates.append(playlist)
        return audio_candidates, video_candidates

    def _timeline_playlist_map(
        self,
        sequence_tractor: ET.Element | None,
        tractors: dict[str, ET.Element],
        playlists: dict[str, ET.Element],
        timeline: TimelineDocument,
    ) -> dict[str, ET.Element]:
        audio_candidates, video_candidates = self._candidate_timeline_playlists(sequence_tractor, tractors, playlists)
        if not audio_candidates or not video_candidates:
            return {}

        audio_order = audio_candidates
        video_primary = video_candidates[-2] if len(video_candidates) >= 2 else video_candidates[0]
        video_order = [video_primary] + [playlist for playlist in video_candidates if playlist is not video_primary]
        result: dict[str, ET.Element] = {}
        audio_tracks = [track for track in timeline.tracks if track.type == "audio"]
        video_tracks = [track for track in timeline.tracks if track.type == "video"]
        if len(audio_tracks) > len(audio_order):
            raise KdenliveProjectError(
                "UNSUPPORTED_TIMELINE",
                f"Template has {len(audio_order)} editable audio playlists but timeline has {len(audio_tracks)} audio tracks.",
            )
        if len(video_tracks) > len(video_order):
            raise KdenliveProjectError(
                "UNSUPPORTED_TIMELINE",
                f"Template has {len(video_order)} editable video playlists but timeline has {len(video_tracks)} video tracks.",
            )
        for track, playlist in zip(audio_tracks, audio_order, strict=False):
            result[track.id] = playlist
        for track, playlist in zip(video_tracks, video_order, strict=False):
            result[track.id] = playlist
        return result
