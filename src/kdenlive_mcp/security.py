from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.config import Settings, get_settings


class SecurityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_user_path(path: str | Path) -> Path:
    raw = Path(path).expanduser()
    return raw.resolve(strict=False)


def ensure_within_allowed(path: str | Path, allowed_roots: tuple[Path, ...], purpose: str) -> Path:
    resolved = resolve_user_path(path)
    if not allowed_roots:
        raise SecurityError(
            "PERMISSION_DENIED",
            f"No allowed {purpose} directories are configured.",
        )

    for root in allowed_roots:
        resolved_root = root.resolve(strict=False)
        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
            return resolved

    raise SecurityError(
        "PERMISSION_DENIED",
        f"Path is outside allowed {purpose} directories: {resolved}",
    )


def ensure_media_path(path: str | Path, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return ensure_within_allowed(path, settings.allowed_media_directories, "media")


def ensure_output_path(path: str | Path, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return ensure_within_allowed(path, settings.allowed_output_directories, "output")


def ensure_project_path(path: str | Path, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return ensure_within_allowed(path, settings.allowed_project_directories, "project")
