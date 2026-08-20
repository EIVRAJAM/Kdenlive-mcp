from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter, KdenliveProjectError
from kdenlive_mcp.security import SecurityError, ensure_output_path, ensure_project_path


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _lock_path(project: Path, lock_directory: Path) -> Path:
    digest = hashlib.sha1(str(project).encode("utf-8")).hexdigest()[:12]
    return lock_directory / f"{project.stem}_{digest}.lock.json"


def _read_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _is_stale(lock: dict[str, Any], stale_after_seconds: int | None) -> bool:
    if stale_after_seconds is None:
        return False
    created_at = _parse_iso(str(lock.get("created_at", "")))
    if created_at is None:
        return True
    age = (_now() - created_at).total_seconds()
    return age > stale_after_seconds


def _project_stats(project: Path) -> dict[str, Any]:
    stat = project.stat()
    return {
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _validated_project(path: str) -> tuple[Path | None, dict[str, Any] | None]:
    try:
        project = ensure_project_path(path)
        KdenliveProjectAdapter().inspect(project)
    except SecurityError as exc:
        return None, _error(exc.code, exc.message)
    except KdenliveProjectError as exc:
        return None, _error(exc.code, exc.message)
    return project, None


def get_project_lock(
    project: str,
    lock_directory: str | None = None,
) -> dict[str, Any]:
    project_path, validation_error = _validated_project(project)
    if validation_error:
        return validation_error
    assert project_path is not None

    try:
        directory = ensure_output_path(lock_directory or str(project_path.parent / ".locks"))
    except SecurityError as exc:
        return _error(exc.code, exc.message)

    path = _lock_path(project_path, directory)
    lock = _read_lock(path)
    return {
        "success": True,
        "operation": "get_project_lock",
        "project": str(project_path),
        "locked": lock is not None,
        "lock_file": str(path),
        "lock": lock,
    }


def lock_project(
    project: str,
    owner: str = "codex",
    lock_directory: str | None = None,
    stale_after_seconds: int | None = None,
) -> dict[str, Any]:
    project_path, validation_error = _validated_project(project)
    if validation_error:
        return validation_error
    assert project_path is not None

    try:
        directory = ensure_output_path(lock_directory or str(project_path.parent / ".locks"))
    except SecurityError as exc:
        return _error(exc.code, exc.message)

    directory.mkdir(parents=True, exist_ok=True)
    path = _lock_path(project_path, directory)
    existing = _read_lock(path)
    if existing is not None:
        if _is_stale(existing, stale_after_seconds):
            path.unlink()
        elif existing.get("owner") == owner:
            return {
                "success": True,
                "operation": "lock_project",
                "project": str(project_path),
                "locked": True,
                "already_locked": True,
                "lock_file": str(path),
                "lock": existing,
            }
        else:
            return _error(
                "PROJECT_LOCKED",
                f"Project is locked by {existing.get('owner')}.",
                project=str(project_path),
                lock_file=str(path),
                lock=existing,
            )

    lock = {
        "project": str(project_path),
        "owner": owner,
        "created_at": _now_iso(),
        "project_stats": _project_stats(project_path),
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(lock, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError:
        return _error("PROJECT_LOCKED", "Project lock was created concurrently.", project=str(project_path))

    return {
        "success": True,
        "operation": "lock_project",
        "project": str(project_path),
        "locked": True,
        "already_locked": False,
        "lock_file": str(path),
        "lock": lock,
    }


def unlock_project(
    project: str,
    owner: str = "codex",
    lock_directory: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    project_path, validation_error = _validated_project(project)
    if validation_error:
        return validation_error
    assert project_path is not None

    try:
        directory = ensure_output_path(lock_directory or str(project_path.parent / ".locks"))
    except SecurityError as exc:
        return _error(exc.code, exc.message)

    path = _lock_path(project_path, directory)
    lock = _read_lock(path)
    if lock is None:
        return {
            "success": True,
            "operation": "unlock_project",
            "project": str(project_path),
            "unlocked": False,
            "lock_file": str(path),
        }

    if lock.get("owner") != owner and not force:
        return _error(
            "PROJECT_LOCKED",
            f"Project is locked by {lock.get('owner')}.",
            project=str(project_path),
            lock_file=str(path),
            lock=lock,
        )

    path.unlink()
    return {
        "success": True,
        "operation": "unlock_project",
        "project": str(project_path),
        "unlocked": True,
        "lock_file": str(path),
        "lock": lock,
    }
