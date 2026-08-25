from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from kdenlive_mcp import __version__


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


class TimelineTrack(BaseModel):
    id: str
    type: Literal["video", "audio"]
    name: str
    locked: bool = False
    muted: bool = False


class TimelineClip(BaseModel):
    id: str
    track_id: str
    media_id: str
    media: str
    source_in: float
    source_out: float
    timeline_in: float
    timeline_out: float
    speed: float = 1.0
    linked_clip_id: str | None = None
    source_segment_id: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "TimelineClip":
        if self.source_in < 0 or self.timeline_in < 0:
            raise ValueError("clip start times must be non-negative")
        if self.source_out <= self.source_in:
            raise ValueError("source_out must be greater than source_in")
        if self.timeline_out <= self.timeline_in:
            raise ValueError("timeline_out must be greater than timeline_in")
        if self.speed <= 0:
            raise ValueError("speed must be greater than zero")
        return self

    @property
    def duration(self) -> float:
        return round(self.timeline_out - self.timeline_in, 6)


class TimelineDocument(BaseModel):
    kind: Literal["kdenlive_mcp_timeline"] = "kdenlive_mcp_timeline"
    schema_version: int = 1
    created_by: str = "kdenlive-mcp"
    created_with_version: str = __version__
    created_at: str = Field(default_factory=utc_now_iso)
    source_plan_file: str | None = None
    source_plan_kind: str | None = None
    fps: float = 30.0
    width: int = 1080
    height: int = 1920
    tracks: list[TimelineTrack] = Field(default_factory=list)
    clips: list[TimelineClip] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timeline(self) -> "TimelineDocument":
        if self.fps <= 0:
            raise ValueError("fps must be greater than zero")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be greater than zero")

        track_ids = {track.id for track in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ValueError("track IDs must be unique")

        clip_ids = {clip.id for clip in self.clips}
        if len(clip_ids) != len(self.clips):
            raise ValueError("clip IDs must be unique")

        for clip in self.clips:
            if clip.track_id not in track_ids:
                raise ValueError(f"clip references unknown track: {clip.track_id}")
            if clip.linked_clip_id is not None and clip.linked_clip_id not in clip_ids:
                raise ValueError(f"clip references unknown linked clip: {clip.linked_clip_id}")
        return self

    @property
    def duration(self) -> float:
        if not self.clips:
            return 0.0
        return round(max(clip.timeline_out for clip in self.clips), 6)
