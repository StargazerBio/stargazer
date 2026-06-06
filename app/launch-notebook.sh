#!/usr/bin/env bash
# Launch script baked into the notebook-app image at
# /usr/local/bin/launch-notebook.sh. Invoked as the per-notebook
# AppEnvironment's args:
#
#     /usr/local/bin/launch-notebook.sh <mode> <notebook_path>
#
# Three things happen on startup:
#
#   1. If the container-local /workspace is empty (no /workspace/.git),
#      clone the user's stargazer fork (default branch, `main`) into it.
#      User notebooks live and persist on `main`; storage is the pod's
#      ephemeral filesystem; the fork is the source of truth.
#   2. Start marimo on 127.0.0.1:8081 in sandbox mode (notebook's PEP 723
#      header drives the venv).
#   3. Start the cookie-validating reverse proxy on 0.0.0.0:8080 (the
#      public port). The proxy also serves /__sg__/workspace/list and
#      /__sg__/workspace/sync straight off the local /workspace directory.
#
# Pending workspace edits are committed and pushed before Knative idles the
# pod by the proxy's FastAPI shutdown hook (uvicorn runs as PID 1 via `exec`
# below, so it receives the Knative SIGTERM). A shell `trap` here would not
# work — `exec` replaces this script, discarding its traps.
set -euo pipefail

MODE="$1"
NOTEBOOK_PATH="$2"

WORKSPACE_DIR="/workspace"

if [ ! -d "${WORKSPACE_DIR}/.git" ]; then
  if [ -z "${FORK_FULL_NAME:-}" ] || [ -z "${SG_POD_TOKEN:-}" ] || [ -z "${STARGAZER_ADMIN_URL:-}" ]; then
    echo "warning: FORK_FULL_NAME/SG_POD_TOKEN/STARGAZER_ADMIN_URL missing; skipping workspace clone" >&2
  else
    # No GitHub credential is baked into this pod. Exchange the signed
    # capability (SG_POD_TOKEN) for a fresh, fork-scoped, ~1h token from the
    # admin, and feed it to git via GIT_ASKPASS so it never lands in argv or
    # .git/config. FORK_FULL_NAME is the verified `owner/repo` (may be `…-1` on
    # a name collision), so clone it directly.
    SG_GIT_TOKEN=$(curl -sf -X POST \
      -H "Authorization: Bearer ${SG_POD_TOKEN}" \
      "${STARGAZER_ADMIN_URL%/}/workspace/pod-token" || true)
    if [ -z "${SG_GIT_TOKEN}" ]; then
      echo "warning: could not fetch fork token from admin; skipping workspace clone" >&2
    else
      ASKPASS=$(mktemp)
      printf '#!/bin/sh\necho "$SG_GIT_TOKEN"\n' > "${ASKPASS}"
      chmod +x "${ASKPASS}"
      echo "Cloning ${FORK_FULL_NAME} into ${WORKSPACE_DIR}..."
      # Username in the URL is the literal `x-access-token` (not a secret); the
      # token comes only from GIT_ASKPASS, so the stored remote stays token-free.
      SG_GIT_TOKEN="${SG_GIT_TOKEN}" GIT_ASKPASS="${ASKPASS}" GIT_TERMINAL_PROMPT=0 \
        git clone --depth 1 \
        "https://x-access-token@github.com/${FORK_FULL_NAME}.git" "${WORKSPACE_DIR}"
      rm -f "${ASKPASS}"
      git -C "${WORKSPACE_DIR}" config user.email "${FORK_OWNER}@users.noreply.github.com"
      git -C "${WORKSPACE_DIR}" config user.name "${FORK_OWNER}"
    fi
  fi
fi

marimo "${MODE}" --sandbox "${NOTEBOOK_PATH}" \
  --port 8081 --host 127.0.0.1 --headless --no-token &

exec uvicorn sg_proxy:asgi_app --host 0.0.0.0 --port 8080
