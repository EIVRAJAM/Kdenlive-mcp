from __future__ import annotations

import json
from pathlib import Path

import pytest

from kdenlive_mcp.config import Settings
from kdenlive_mcp.security import SecurityError, ensure_media_path, ensure_output_path, ensure_project_path
from kdenlive_mcp.server import handle_request


ENSURE_FUNCS = {
    "media": ensure_media_path,
    "project": ensure_project_path,
    "output": ensure_output_path,
}
ALLOWED_FIELD = {
    "media": "allowed_media_directories",
    "project": "allowed_project_directories",
    "output": "allowed_output_directories",
}


def _settings(roots: tuple[Path, ...], *, field: str) -> Settings:
    kwargs: dict[str, object] = {
        "allowed_media_directories": tuple(),
        "allowed_project_directories": tuple(),
        "allowed_output_directories": tuple(),
    }
    kwargs[field] = tuple(root.resolve() for root in roots)
    return Settings(**kwargs)  # type: ignore[arg-type]


def _make_tree(tmp_path: Path) -> tuple[Path, Path]:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "media.mp4").write_bytes(b"x")
    (allowed / "inside").mkdir()
    return allowed, outside


@pytest.mark.parametrize("category", ["media", "project", "output"])
def test_parent_traversal_is_rejected(tmp_path: Path, category: str) -> None:
    allowed, _outside = _make_tree(tmp_path)
    settings = _settings((allowed,), field=ALLOWED_FIELD[category])
    target = allowed / ".." / "escape"

    with pytest.raises(SecurityError) as excinfo:
        ENSURE_FUNCS[category](target, settings=settings)
    assert excinfo.value.code == "PERMISSION_DENIED"


@pytest.mark.parametrize("category", ["media", "project", "output"])
def test_symlink_escaping_allowlist_is_rejected(tmp_path: Path, category: str) -> None:
    allowed, outside = _make_tree(tmp_path)
    link = allowed / "link_to_outside"
    link.symlink_to(outside)
    settings = _settings((allowed,), field=ALLOWED_FIELD[category])
    target = link / "media.mp4"

    with pytest.raises(SecurityError) as excinfo:
        ENSURE_FUNCS[category](target, settings=settings)
    assert excinfo.value.code == "PERMISSION_DENIED"


@pytest.mark.parametrize("category", ["media", "project", "output"])
def test_symlink_staying_inside_allowlist_is_accepted(tmp_path: Path, category: str) -> None:
    allowed, _outside = _make_tree(tmp_path)
    link = allowed / "link_to_inside"
    link.symlink_to("inside")
    settings = _settings((allowed,), field=ALLOWED_FIELD[category])
    target = link / "media.mp4"

    resolved = ENSURE_FUNCS[category](target, settings=settings)
    assert resolved == allowed.resolve() / "inside" / "media.mp4"


@pytest.mark.parametrize("category", ["media", "project", "output"])
def test_empty_allowlist_is_rejected(tmp_path: Path, category: str) -> None:
    settings = _settings(tuple(), field=ALLOWED_FIELD[category])

    with pytest.raises(SecurityError) as excinfo:
        ENSURE_FUNCS[category](tmp_path / "anything.mp4", settings=settings)
    assert excinfo.value.code == "PERMISSION_DENIED"


def test_media_tool_rejects_symlink_escaping_allowlist_via_mcp(monkeypatch, tmp_path: Path) -> None:
    allowed, outside = _make_tree(tmp_path)
    link = allowed / "link_to_outside"
    link.symlink_to(outside)
    monkeypatch.setenv("KDENLIVE_MCP_ALLOWED_MEDIA_DIRS", str(allowed.resolve()))
    monkeypatch.setenv("KDENLIVE_MCP_LOG_FILE", "off")

    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": "security",
            "method": "tools/call",
            "params": {"name": "get_media_info", "arguments": {"media": str(link / "media.mp4")}},
        }
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["success"] is False
    assert payload["error"] == "PERMISSION_DENIED"
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["operation"] == "get_media_info"