#!/usr/bin/env bash
# Launch script for notebook pods: baked at /usr/local/bin/launch-notebook.sh
# in the Stargazer image (runtime/Dockerfile).
# Invoked as the per-notebook AppEnvironment's args:
#
#     /usr/local/bin/launch-notebook.sh <mode> <notebook_path>
#
# Run locally, the image's entrypoint (start-local.sh) passes the Assets
# tutorial, with the rest of its notebooks beside it in /workspace.
#
# Four things happen on startup:
#
#   1. Hydrate: copy the owner's whole workspace from the workspace store into
#      /workspace, and their agent sign-ins into the home directory, via the
#      proxy module's `hydrate()`. A new user, or a deploy
#      without a store, starts with an empty dir. The session then cd's into
#      /workspace so marimo, its terminal and its agent all work there.
#   2. Start marimo on 127.0.0.1:8081 in sandbox mode (notebook's PEP 723
#      header drives the venv), watching the notebook's file in edit mode.
#   3. In edit mode, start the `stargazer` MCP server on 127.0.0.1:8000, which
#      the proxy hands to each agent session in marimo's agent panel.
#   4. Start the reverse proxy on 0.0.0.0:8080 (the public port).
#      It also writes changed files back to the store on an interval.
#
# Pending workspace edits are saved one last time before Knative idles the pod
# by the proxy's FastAPI shutdown hook, which fires on SIGTERM. For that to
# work the proxy (uvicorn) must be the process Flyte's `fserve` wrapper signals.
# `fserve` is PID 1; it runs this script via `Popen(cmd, shell=True)` and on
# SIGTERM forwards the signal to that ONE direct child only (it does not signal
# the whole tree). So uvicorn must end up as `fserve`'s direct child:
#   - The AppEnvironment args prepend `exec` (the dashboard's launch), so the
#     `sh -c` wrapper `fserve` spawns replaces itself with this script instead
#     of lingering as an intermediate shell. (Debian's /bin/sh does not always
#     exec-collapse a bare `sh -c "script"`; the explicit `exec` guarantees it.)
#   - This script then `exec`s uvicorn below, so uvicorn inherits that same
#     direct-child slot and receives the forwarded SIGTERM, running the flush.
# An intermediate shell anywhere in this chain swallows SIGTERM and the flush is
# silently skipped — losing unsaved edits at scale-to-zero.
set -euo pipefail

MODE="$1"
NOTEBOOK_PATH="$2"

WORKSPACE_DIR="/workspace"

# A failed hydrate must not stop the pod from serving: the user still gets
# their notebook environment, just without previously saved files. Logged so
# it's diagnosable.
python -c "import sg_proxy; sg_proxy.hydrate()" \
  || echo "warning: could not load saved notebooks; starting with an empty workspace" >&2

# Work directly in the workspace dir. marimo (backgrounded) and the proxy
# (exec'd) both inherit this cwd, so marimo's terminal and the agents the proxy
# starts for its agent panel open here.
cd "${WORKSPACE_DIR}" 2>/dev/null || true

# A workspace notebook that didn't hydrate is gone from the store: deleted while
# this pod started, or the hydrate failed. marimo opens a blank one in its
# place, which the proxy never saves, so it can't undo the delete or overwrite
# the stored notebook.
if [[ "${NOTEBOOK_PATH}" == "${WORKSPACE_DIR}/"* && ! -e "${NOTEBOOK_PATH}" ]]; then
  export SG_UNSAVED_NOTEBOOK="${NOTEBOOK_PATH#"${WORKSPACE_DIR}/"}"
fi

# `--watch` brings the agent's edits to the open notebook into the editor,
# which otherwise keeps its own copy and saves it back over them.
WATCH=()
[[ "${MODE}" == "edit" ]] && WATCH=(--watch)

# `-q`: marimo's banner advertises its own port, 8081, which only the proxy
# can reach.
marimo -q "${MODE}" --sandbox "${WATCH[@]}" "${NOTEBOOK_PATH}" \
  --port 8081 --host 127.0.0.1 --headless --no-token &

# The agents' env has no project key (the proxy's `_agent_env`), so the server
# runs here, with the pod's whole env, where it can start runs in the owner's
# project. The panel is edit mode's only.
if [[ "${MODE}" == "edit" ]]; then
  /opt/mcp/bin/stargazer --http &
fi

# `--timeout-graceful-shutdown` is required for the shutdown flush to run, not
# just a tuning knob. On SIGTERM uvicorn drains open connections and in-flight
# background tasks BEFORE firing the FastAPI `lifespan` shutdown (the final save
# of workspace edits). The proxy holds a long-lived task to the local marimo
# backend that does not drain on its own, so with the uvicorn default
# (`timeout_graceful_shutdown=None`) the drain waits forever and the flush never
# runs — verified empirically: the pod sat at "Waiting for background tasks to
# complete" indefinitely, even after the browser tab closed. A bounded timeout
# makes uvicorn cancel the lingering task and then still run `lifespan.shutdown`
# (it only skips the flush on a *second* SIGTERM / force-quit). 15s leaves ample
# room for the upload under the pod's 300s termination grace period.
exec uvicorn sg_proxy:asgi_app --host 0.0.0.0 --port 8080 \
  --timeout-graceful-shutdown 15
