from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kdenlive_mcp.domain.manifest import ManifestMediaItem, ProjectManifest
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path
from kdenlive_mcp.tools.media_tools import scan_media


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": code, "message": message, **extra}


def _security_error(exc: SecurityError) -> dict[str, Any]:
    return _error(exc.code, exc.message)


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    slug = slug.strip("._-")
    return slug or "kdenlive_mcp_manifest"


def media_id_for_path(path: str) -> str:
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]
    return f"media_{digest}"


def manifest_path_for(directory: Path, name: str) -> Path:
    return directory / f"{slugify_name(name)}.kdenlive-mcp.json"


def load_manifest(path: Path) -> ProjectManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectManifest.model_validate(data)


def save_manifest(path: Path, manifest: ProjectManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        manifest.model_dump_json(indent=2, exclude_none=True) + "\n",
        encoding="utf-8",
    )


def create_manifest(
    name: str,
    output_directory: str,
    description: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        output_dir = ensure_output_path(output_directory)
    except SecurityError as exc:
        return _security_error(exc)
    path = manifest_path_for(output_dir, name)
    if path.exists() and not overwrite:
        return _error("OUTPUT_EXISTS", f"Manifest already exists: {path}")

    manifest = ProjectManifest(name=name, description=description)
    save_manifest(path, manifest)
    return {
        "success": True,
        "operation": "create_manifest",
        "manifest": str(path),
        "data": manifest.model_dump(mode="json", exclude_none=True),
    }


def inspect_manifest(manifest: str) -> dict[str, Any]:
    try:
        path = ensure_output_path(manifest)
    except SecurityError as exc:
        return _security_error(exc)
    if not path.exists():
        return _error("MANIFEST_NOT_FOUND", f"Manifest does not exist: {path}")
    try:
        data = load_manifest(path)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_MANIFEST", f"Manifest is invalid: {exc}")
    return {
        "success": True,
        "operation": "inspect_manifest",
        "manifest": str(path),
        "data": data.model_dump(mode="json", exclude_none=True),
    }


def validate_manifest(manifest: str) -> dict[str, Any]:
    inspected = inspect_manifest(manifest)
    if not inspected.get("success"):
        return inspected
    data = ProjectManifest.model_validate(inspected["data"])
    missing_media = [item.path for item in data.media if not Path(item.path).exists()]
    duplicate_ids = sorted(
        media_id
        for media_id in {item.id for item in data.media}
        if sum(1 for item in data.media if item.id == media_id) > 1
    )
    return {
        "success": True,
        "operation": "validate_manifest",
        "manifest": inspected["manifest"],
        "valid": not missing_media and not duplicate_ids,
        "media_count": len(data.media),
        "missing_media": missing_media,
        "duplicate_ids": duplicate_ids,
    }


def scan_media_to_manifest(
    manifest: str,
    folder: str,
    recursive: bool = True,
    replace: bool = True,
) -> dict[str, Any]:
    try:
        manifest_path = ensure_output_path(manifest)
        source_folder = ensure_media_path(folder)
    except SecurityError as exc:
        return _security_error(exc)
    if not manifest_path.exists():
        return _error("MANIFEST_NOT_FOUND", f"Manifest does not exist: {manifest_path}")

    scan = scan_media(str(source_folder), recursive=recursive, probe=True)
    if not scan.get("success"):
        return scan

    try:
        data = load_manifest(manifest_path)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _error("INVALID_MANIFEST", f"Manifest is invalid: {exc}")

    scanned_items = [
        ManifestMediaItem(id=media_id_for_path(item["path"]), **item)
        for item in scan["media"]
    ]
    if replace:
        data.media = scanned_items
    else:
        existing = {item.id: item for item in data.media}
        for item in scanned_items:
            existing[item.id] = item
        data.media = sorted(existing.values(), key=lambda item: item.path)
    data.source_folder = str(source_folder)
    data.touch()
    save_manifest(manifest_path, data)

    return {
        "success": True,
        "operation": "scan_media_to_manifest",
        "manifest": str(manifest_path),
        "source_folder": str(source_folder),
        "replace": replace,
        "media_count": len(data.media),
        "failure_count": scan["failure_count"],
        "data": data.model_dump(mode="json", exclude_none=True),
        "failures": scan["failures"],
    }
