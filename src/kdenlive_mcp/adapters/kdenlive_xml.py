from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


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
