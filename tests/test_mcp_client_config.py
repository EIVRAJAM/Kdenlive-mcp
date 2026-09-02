from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERIC_CONFIG = REPO_ROOT / "examples" / "mcp_client_config.toml"
CODEX_CONFIG = REPO_ROOT / "examples" / "codex_mcp_config.toml"

DANGEROUS_ROOTS = {"/", "/etc", "/usr", "/boot", "~/.ssh"}

ALLOWLIST_KEYS = (
    "KDENLIVE_MCP_ALLOWED_MEDIA_DIRS",
    "KDENLIVE_MCP_ALLOWED_PROJECT_DIRS",
    "KDENLIVE_MCP_ALLOWED_OUTPUT_DIRS",
)


def _load(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _kdenlive_server(path: Path) -> dict[str, object]:
    config = _load(path)
    servers = config["mcp_servers"]
    assert isinstance(servers, dict)
    assert "kdenlive" in servers
    server = servers["kdenlive"]
    assert isinstance(server, dict)
    return server


def test_generic_mcp_client_config_parses() -> None:
    assert _kdenlive_server(GENERIC_CONFIG)


def test_generic_config_has_expected_command_args_and_env() -> None:
    server = _kdenlive_server(GENERIC_CONFIG)

    assert server["command"] == "kdenlive-mcp"
    assert server["args"] == []
    env = server["env"]
    assert isinstance(env, dict)
    for key in ALLOWLIST_KEYS:
        assert env.get(key), f"missing {key}"


def test_generic_config_allowlists_avoid_dangerous_roots() -> None:
    env = _kdenlive_server(GENERIC_CONFIG)["env"]
    assert isinstance(env, dict)

    for key in ALLOWLIST_KEYS:
        for part in str(env[key]).split(":"):
            assert part not in DANGEROUS_ROOTS, f"{key} contains dangerous root: {part}"


def test_codex_config_stays_aligned_with_generic() -> None:
    codex_server = _kdenlive_server(CODEX_CONFIG)
    generic_server = _kdenlive_server(GENERIC_CONFIG)

    assert codex_server["command"] == generic_server["command"]
    assert codex_server["args"] == generic_server["args"]
    codex_env = codex_server["env"]
    generic_env = generic_server["env"]
    assert isinstance(codex_env, dict) and isinstance(generic_env, dict)
    assert set(codex_env) == set(generic_env)

    codex_env = codex_env
    for key in ALLOWLIST_KEYS:
        for part in str(codex_env[key]).split(":"):
            assert part not in DANGEROUS_ROOTS, f"{key} contains dangerous root: {part}"