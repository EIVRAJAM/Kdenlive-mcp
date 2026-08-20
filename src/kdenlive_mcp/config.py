from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_paths(value: str | None) -> tuple[Path, ...]:
    if not value:
        return tuple()
    return tuple(Path(item).expanduser().resolve() for item in value.split(":") if item)


@dataclass(frozen=True)
class Settings:
    allowed_media_directories: tuple[Path, ...]
    allowed_project_directories: tuple[Path, ...]
    allowed_output_directories: tuple[Path, ...]
    kdenlive_flatpak_id: str = "org.kde.kdenlive"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            allowed_media_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS")),
            allowed_project_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS")),
            allowed_output_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS")),
            kdenlive_flatpak_id=os.getenv("KDENLIVE_MCP_FLATPAK_ID", "org.kde.kdenlive"),
        )


def get_settings() -> Settings:
    return Settings.from_environment()
