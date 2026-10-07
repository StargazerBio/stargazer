#!/usr/bin/env bash
# Read-only health check for a verify-stargazer run. Prints one line per check.
# Exit 1 if a check every local drive depends on fails; devbox and CLI tools
# are reported but only gate the features that need them.
set -uo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
CACHE="${VERIFY_CACHE:-$HOME/.stargazer/verify-cache}"
fail=0

ok()   { printf 'ok    %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; fail=1; }
note() { printf 'info  %s\n' "$1"; }

cd "$ROOT" || exit 1

if uv run python -c "import stargazer" >/dev/null 2>&1; then ok "stargazer importable in uv env"; else bad "stargazer not importable: run 'uv sync'"; fi
for bin in flyte marimo; do
  if uv run which "$bin" >/dev/null 2>&1; then ok "$bin in uv env"; else bad "$bin missing from uv env"; fi
done

check_path() {  # name, the user's default it must not equal
  local name="$1" default="$2" value="${!1:-}"
  if [[ -z "$value" ]]; then
    bad "$name unset: export it to this run's directory"
  elif [[ "$value" == "$default" ]]; then
    bad "$name is the user's default: use a run directory"
  else
    ok "$name=$value"
  fi
}
check_path STARGAZER_LOCAL "$HOME/.stargazer/local"
check_path STARGAZER_STORE_ROOT "$HOME/.stargazer/store"
check_path STARGAZER_INDEX_URL "$HOME/.stargazer/index.db"

# marimo loads .env, which holds a PINATA_JWT. An explicitly empty value wins
# over the .env entry and keeps outputs local.
if [[ "${PINATA_JWT+set}" == "set" && -z "$PINATA_JWT" ]]; then
  ok "PINATA_JWT explicitly empty (no public tier; outputs stay in the run)"
else
  bad "PINATA_JWT not explicitly empty: export PINATA_JWT= so drives stay inside the run"
fi

for cid in $(grep -o 'bafy[a-z0-9]*' src/stargazer/bundles/scrna_demo.yaml); do
  if [[ -s "$CACHE/$cid" ]]; then ok "scrna_demo cached: $cid"; else note "scrna_demo not cached: $cid (seed_scrna.py will download it)"; fi
done

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${DEVBOX_CONTAINER:-flyte-devbox}"; then
  ok "devbox container running"
else
  note "devbox container not running: remote features unreachable"
fi

for tool in bwa samtools gatk; do
  if command -v "$tool" >/dev/null 2>&1; then ok "$tool on PATH"; else note "$tool not on PATH: local GATK/general tasks unreachable"; fi
done

exit $fail
