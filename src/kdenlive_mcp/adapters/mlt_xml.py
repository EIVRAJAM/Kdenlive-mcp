from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument


def seconds_to_timecode(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def seconds_to_frame(seconds: float, fps: float, inclusive_end: bool = False) -> int:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    frame = int(round(seconds * fps))
    if inclusive_end:
        return max(0, frame - 1)
    return frame


def _property(parent: ET.Element, name: str, value: str | int | float) -> ET.Element:
    element = ET.SubElement(parent, "property", {"name": name})
    element.text = str(value)
    return element


def _media_ids(timeline: TimelineDocument) -> list[tuple[str, str]]:
    media_by_id: dict[str, str] = {}
    for clip in timeline.clips:
        media_by_id.setdefault(clip.media_id, clip.media)
    return sorted(media_by_id.items(), key=lambda item: item[0])


def _playlist_entries(playlist: ET.Element, clips: list[TimelineClip], fps: float) -> None:
    cursor = 0.0
    for clip in sorted(clips, key=lambda item: (item.timeline_in, item.timeline_out, item.id)):
        if clip.timeline_in > cursor:
            ET.SubElement(
                playlist,
                "blank",
                {"length": str(seconds_to_frame(clip.timeline_in - cursor, fps))},
            )
        ET.SubElement(
            playlist,
            "entry",
            {
                "producer": clip.media_id,
                "in": str(seconds_to_frame(clip.source_in, fps)),
                "out": str(seconds_to_frame(clip.source_out, fps, inclusive_end=True)),
            },
        )
        cursor = max(cursor, clip.timeline_out)


def timeline_to_mlt_xml(timeline: TimelineDocument) -> ET.ElementTree:
    root = ET.Element(
        "mlt",
        {
            "LC_NUMERIC": "C",
            "version": "7.0.0",
            "title": "kdenlive-mcp timeline draft",
            "producer": "main_tractor",
        },
    )
    ET.SubElement(
        root,
        "profile",
        {
            "description": "kdenlive-mcp generated draft",
            "width": str(timeline.width),
            "height": str(timeline.height),
            "progressive": "1",
            "sample_aspect_num": "1",
            "sample_aspect_den": "1",
            "display_aspect_num": "9" if timeline.width == 1080 and timeline.height == 1920 else str(timeline.width),
            "display_aspect_den": "16" if timeline.width == 1080 and timeline.height == 1920 else str(timeline.height),
            "frame_rate_num": str(int(round(timeline.fps))),
            "frame_rate_den": "1",
            "colorspace": "709",
        },
    )

    for media_id, media_path in _media_ids(timeline):
        producer = ET.SubElement(root, "producer", {"id": media_id})
        _property(producer, "resource", media_path)
        _property(producer, "mlt_service", "avformat")

    for track in timeline.tracks:
        playlist = ET.SubElement(root, "playlist", {"id": track.id})
        _property(playlist, "kdenlive:mcp_track_type", track.type)
        _playlist_entries(playlist, [clip for clip in timeline.clips if clip.track_id == track.id], timeline.fps)

    tractor = ET.SubElement(
        root,
        "tractor",
        {
            "id": "main_tractor",
            "in": "0",
            "out": str(seconds_to_frame(timeline.duration, timeline.fps, inclusive_end=True)),
        },
    )
    for track in timeline.tracks:
        ET.SubElement(tractor, "track", {"producer": track.id})

    return ET.ElementTree(root)


def write_mlt_xml(path: Path, timeline: TimelineDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = timeline_to_mlt_xml(timeline)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
