from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kdenlive_mcp.config import get_settings


SENSITIVE_KEY_PARTS = ("token", "secret", "password", "key", "credential")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _artifact_paths(result: dict[str, Any]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key in ("project", "timeline_file", "plan_file", "mlt_xml", "working_project", "backup", "lock_file"):
        if key in result:
            artifacts[key] = result[key]
    if isinstance(result.get("artifacts"), dict):
        artifacts["artifacts"] = result["artifacts"]
    if isinstance(result.get("partial_outputs"), dict):
        artifacts["partial_outputs"] = result["partial_outputs"]
    return artifacts


def append_tool_log(
    *,
    request_id: Any,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    duration_ms: float,
) -> None:
    settings = get_settings()
    if settings.log_file is None:
        return

    record = {
        "timestamp": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
        "event": "tool_call",
        "request_id": request_id,
        "operation": tool_name,
        "duration_ms": round(duration_ms, 3),
        "success": bool(result.get("success", False)),
        "error": result.get("error"),
        "arguments": _redact(arguments),
        "artifacts": _artifact_paths(result),
    }
    path = Path(settings.log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
