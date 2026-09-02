#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SUMMARY=()
GATES=()

run_gate() {
  local label="$1"
  shift
  echo "==> [$label] $*"
  "$@"
  SUMMARY+=("$label: OK")
  GATES+=("$label")
}

echo "=== kdenlive-mcp release gate ==="

# 1. Deterministic local checks (compileall + pytest)
run_gate "dev_check" bash scripts/dev_check.sh

# 2. Real STDIO smoke test (initialize + tools/list over Content-Length framing)
run_gate "stdio_smoke" env KDENLIVE_MCP_RUN_STDIO_SMOKE=1 scripts/dev_check.sh

# 3. Fixture reliability (20 runs, checksums unchanged, overwrite refusal)
run_gate "reliability" env KDENLIVE_MCP_RUN_RELIABILITY=1 scripts/dev_check.sh

# 4. Optional real MLT load gate
MLT_PROJECT="${KDENLIVE_MCP_MLT_PROJECT:-}"
if [[ -n "$MLT_PROJECT" ]]; then
  run_gate "mlt_load" env KDENLIVE_MCP_RUN_MLT_CHECK=1 KDENLIVE_MCP_MLT_PROJECT="$MLT_PROJECT" scripts/dev_check.sh
else
  echo "==> [mlt_load] SKIPPED: KDENLIVE_MCP_MLT_PROJECT not set."
  echo "    Set it to a generated .kdenlive to run the real Flatpak melt gate."
  SUMMARY+=("mlt_load: SKIPPED (KDENLIVE_MCP_MLT_PROJECT unset)")
fi

echo ""
echo "=== Release gate summary ==="
printf '%s\n' "${SUMMARY[@]}"
echo ""
if [[ -z "$MLT_PROJECT" ]]; then
  echo "Manual steps still required:"
  echo "  - Flatpak melt load check (set KDENLIVE_MCP_MLT_PROJECT and rerun)"
  echo "  - Manual Kdenlive open verification"
else
  echo "Manual step still required:"
  echo "  - Manual Kdenlive open verification"
fi