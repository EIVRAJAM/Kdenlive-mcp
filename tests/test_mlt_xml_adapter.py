from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from kdenlive_mcp.adapters.mlt_xml import seconds_to_frame, seconds_to_timecode, timeline_to_mlt_xml
from kdenlive_mcp.domain.timeline import TimelineClip, TimelineDocument, TimelineTrack


def _timeline() -> TimelineDocument:
    return TimelineDocument(
        fps=30,
        width=1080,
        height=1920,
        tracks=[
            TimelineTrack(id="track_v1", type="video", name="Video 1"),
            TimelineTrack(id="track_a1", type="audio", name="Audio 1"),
        ],
        clips=[
            TimelineClip(
                id="clip_001_v",
                track_id="track_v1",
                media_id="media_a",
                media="/tmp/a.mp4",
                source_in=1.0,
                source_out=2.0,
                timeline_in=0.0,
                timeline_out=1.0,
                linked_clip_id="clip_001_a",
            ),
            TimelineClip(
                id="clip_001_a",
                track_id="track_a1",
                media_id="media_a",
                media="/tmp/a.mp4",
                source_in=1.0,
                source_out=2.0,
                timeline_in=0.0,
                timeline_out=1.0,
                linked_clip_id="clip_001_v",
            ),
            TimelineClip(
                id="clip_002_v",
                track_id="track_v1",
                media_id="media_b",
                media="/tmp/b.mp4",
                source_in=0.0,
                source_out=1.0,
                timeline_in=2.0,
                timeline_out=3.0,
                linked_clip_id="clip_002_a",
            ),
            TimelineClip(
                id="clip_002_a",
                track_id="track_a1",
                media_id="media_b",
                media="/tmp/b.mp4",
                source_in=0.0,
                source_out=1.0,
                timeline_in=2.0,
                timeline_out=3.0,
                linked_clip_id="clip_002_v",
            ),
        ],
    )


def test_seconds_to_timecode() -> None:
    assert seconds_to_timecode(0) == "00:00:00.000"
    assert seconds_to_timecode(65.25) == "00:01:05.250"
    with pytest.raises(ValueError):
        seconds_to_timecode(-1)


def test_seconds_to_frame() -> None:
    assert seconds_to_frame(0, 30) == 0
    assert seconds_to_frame(1.0, 30) == 30
    assert seconds_to_frame(1.0, 30, inclusive_end=True) == 29
    with pytest.raises(ValueError):
        seconds_to_frame(1.0, 0)


def test_timeline_to_mlt_xml_contains_tracks_entries_and_blanks() -> None:
    root = timeline_to_mlt_xml(_timeline()).getroot()

    assert root.tag == "mlt"
    assert root.attrib["producer"] == "main_tractor"
    assert root.find("profile").attrib["width"] == "1080"
    producers = {producer.attrib["id"] for producer in root.findall("producer")}
    assert producers == {"media_a", "media_b"}

    video_playlist = root.find("playlist[@id='track_v1']")
    assert video_playlist is not None
    children = [child for child in video_playlist if child.tag in {"entry", "blank"}]
    assert [child.tag for child in children if child.tag in {"entry", "blank"}] == ["entry", "blank", "entry"]
    assert children[0].attrib["producer"] == "media_a"
    assert children[0].attrib["in"] == "30"
    assert children[0].attrib["out"] == "59"
    assert children[1].attrib["length"] == "30"


def test_written_mlt_xml_is_well_formed(tmp_path: Path) -> None:
    path = tmp_path / "timeline.mlt.xml"
    from kdenlive_mcp.adapters.mlt_xml import write_mlt_xml

    write_mlt_xml(path, _timeline())

    parsed = ET.parse(path)
    assert parsed.getroot().tag == "mlt"
