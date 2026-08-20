from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from kdenlive_mcp import __version__


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


class ManifestMediaItem(BaseModel):
    id: str
    path: str
    filename: str
    extension: str
    size_bytes: int | None = None
    duration_seconds: float | None = None
    format_name: str | None = None
    bitrate: float | None = None
    video: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectManifest(BaseModel):
    schema_version: str = "1.0"
    created_by: str = "kdenlive-mcp"
    created_with_version: str = __version__
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    name: str
    description: str | None = None
    source_folder: str | None = None
    media: list[ManifestMediaItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()
