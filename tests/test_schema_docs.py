from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = REPO_ROOT / "docs" / "SCHEMAS.md"


def test_schemas_doc_has_migration_policy_section() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    assert "## Schema Migration Policy" in text


def test_migration_policy_mentions_unsupported_schema_version_code() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    assert "UNSUPPORTED_SCHEMA_VERSION" in text


def test_migration_policy_mentions_dry_run() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    assert "dry_run" in text


def test_migration_policy_mentions_backup_before_migration() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    assert "backup" in text


def test_migration_policy_covers_all_persisted_kinds() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    assert "kdenlive_mcp_rough_cut_plan" in text
    assert "kdenlive_mcp_timeline" in text
    assert "kdenlive-mcp.json" in text