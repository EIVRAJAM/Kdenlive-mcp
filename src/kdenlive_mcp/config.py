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
    log_file: Path | None = Path("logs/kdenlive-mcp.log")

    @classmethod
    def from_environment(cls) -> "Settings":
        log_file_value = os.getenv("KDENLIVE_MCP_LOG_FILE")
        log_file = Path(log_file_value).expanduser().resolve() if log_file_value else Path("logs/kdenlive-mcp.log")
        if log_file_value is not None and log_file_value.lower() in {"", "0", "false", "none", "off"}:
            log_file = None
        return cls(
            allowed_media_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS")),
            allowed_project_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_PROJECT_DIRS")),
            allowed_output_directories=_split_paths(os.getenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS")),
            kdenlive_flatpak_id=os.getenv("KDENLIVE_MCP_FLATPAK_ID", "org.kde.kdenlive"),
            log_file=log_file,
        )


def get_settings() -> Settings:
    return Settings.from_environment()
