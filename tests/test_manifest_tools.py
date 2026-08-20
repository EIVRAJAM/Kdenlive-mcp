from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.services.manifest_service import media_id_for_path, slugify_name
from kdenlive_mcp.tools import manifest_tools


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"
SAMPLE_VIDEO = RECON_DIR / "sample1.mp4"


def _allow(monkeypatch, output_dir: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(RECON_DIR))
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(output_dir))


def test_slugify_name() -> None:
    assert slugify_name("Vlog Santa Marta") == "Vlog_Santa_Marta"
    assert slugify_name("...") == "kdenlive_mcp_manifest"


def test_media_id_for_path_is_stable() -> None:
    first = media_id_for_path(str(SAMPLE_VIDEO))
    second = media_id_for_path(str(SAMPLE_VIDEO))

    assert first == second
    assert first.startswith("media_")


def test_create_inspect_validate_manifest(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)

    created = manifest_tools.create_manifest(
        name="Vlog Santa Marta",
        output_directory=str(tmp_path),
        description="Recon manifest",
    )

    assert created["success"] is True
    manifest_path = Path(created["manifest"])
    assert manifest_path.exists()
    assert manifest_path.name == "Vlog_Santa_Marta.kdenlive-mcp.json"

    inspected = manifest_tools.inspect_manifest(manifest=str(manifest_path))
    assert inspected["success"] is True
    assert inspected["data"]["name"] == "Vlog Santa Marta"
    assert inspected["data"]["description"] == "Recon manifest"

    validated = manifest_tools.validate_manifest(manifest=str(manifest_path))
    assert validated["success"] is True
    assert validated["valid"] is True
    assert validated["media_count"] == 0


def test_create_manifest_refuses_existing_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    handler = manifest_tools.create_manifest

    first = handler(name="Existing", output_directory=str(tmp_path))
    second = handler(name="Existing", output_directory=str(tmp_path))

    assert first["success"] is True
    assert second["success"] is False
    assert second["error"] == "OUTPUT_EXISTS"


def test_scan_media_to_manifest(monkeypatch, tmp_path: Path) -> None:
    _allow(monkeypatch, tmp_path)
    manifest_path = Path(
        manifest_tools.create_manifest(
            name="Recon",
            output_directory=str(tmp_path),
        )["manifest"]
    )

    result = manifest_tools.scan_media_to_manifest(
        manifest=str(manifest_path),
        folder=str(RECON_DIR),
    )

    assert result["success"] is True
    assert result["media_count"] >= 2
    filenames = {item["filename"] for item in result["data"]["media"]}
    assert {"sample1.mp4", "sample_vertical.mp4"}.issubset(filenames)

    validated = manifest_tools.validate_manifest(manifest=str(manifest_path))
    assert validated["success"] is True
    assert validated["valid"] is True
    assert validated["missing_media"] == []


def test_manifest_output_allowlist_required(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS", str(tmp_path / "allowed"))

    result = manifest_tools.create_manifest(
        name="Denied",
        output_directory=str(tmp_path / "denied"),
    )

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"
