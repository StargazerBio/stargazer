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
#      clone the user's stargazer fork into it. Storage is the pod's
#      ephemeral filesystem; the fork is the source of truth.
#   2. Start marimo on 127.0.0.1:8081 in sandbox mode (notebook's PEP 723
#      header drives the venv).
#   3. Start the cookie-validating reverse proxy on 0.0.0.0:8080 (the
#      public port). The proxy also serves /__sg__/workspace/list and
#      /__sg__/workspace/sync straight off the local /workspace directory.
#
# A SIGTERM trap calls the local /__sg__/workspace/sync route so any
# pending workspace edits get committed and pushed before Knative idles
# the pod.
set -euo pipefail

MODE="$1"
NOTEBOOK_PATH="$2"

WORKSPACE_DIR="/workspace"

if [ ! -d "${WORKSPACE_DIR}/.git" ]; then
  if [ -z "${FORK_OWNER:-}" ] || [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "warning: FORK_OWNER or GITHUB_TOKEN missing; skipping workspace clone" >&2
  else
    UPSTREAM="${STARGAZER_UPSTREAM_REPO:-StargazerBio/stargazer}"
    REPO_NAME="${UPSTREAM##*/}"
    CLONE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${FORK_OWNER}/${REPO_NAME}.git"
    echo "Cloning ${FORK_OWNER}/${REPO_NAME} into ${WORKSPACE_DIR}..."
    git clone --depth 1 "${CLONE_URL}" "${WORKSPACE_DIR}"
    git -C "${WORKSPACE_DIR}" config user.email "${FORK_OWNER}@users.noreply.github.com"
    git -C "${WORKSPACE_DIR}" config user.name "${FORK_OWNER}"
  fi
fi

flush_workspace() {
  # Best-effort; never block shutdown.
  curl -fsS -X POST --max-time 10 \
    -H "X-Sg-Reason: notebook-shutdown" \
    http://127.0.0.1:8080/__sg__/workspace/sync || true
}

trap 'flush_workspace; kill -TERM "$MARIMO_PID" 2>/dev/null || true; exit 0' TERM INT

marimo "${MODE}" --sandbox "${NOTEBOOK_PATH}" \
  --port 8081 --host 127.0.0.1 --headless --no-token &
MARIMO_PID=$!

exec uvicorn app.proxy:asgi_app --host 0.0.0.0 --port 8080
