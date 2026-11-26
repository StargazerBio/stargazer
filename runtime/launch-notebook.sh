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
# With `SG_NOTEBOOK_MANIFEST` set (a hosted workspace notebook), the notebook is
# its own volume, mounted by the proxy at the notebook's folder, so the
# notebook's path is /workspace/<slug>/<file>. With none (a built-in notebook,
# locally) nothing is mounted and the notebook is a plain file.
#
# Four things happen on startup:
#
#   1. Put the owner's agent sign-ins back in the home directory, via the
#      proxy module's `restore_sign_ins()`. A new user, or a deploy without a
#      store, restores none.
#   2. In the background, wait for the notebook's file to exist, which for a
#      volume is the proxy mounting it (step 4), then pin the header's Python
#      to the image's own minor version when it pins none, so pixi's sandbox
#      doesn't take conda-forge's newest and fail, and copy an old header's uv
#      source for the SDK to where pixi reads it. Then start marimo on
#      127.0.0.1:8081 in pixi's sandbox mode (the notebook's PEP 723 header
#      drives its environment, conda and PyPI packages both), watching the
#      notebook's file in edit mode, in a volume notebook's folder (else in
#      /workspace), so marimo's terminal and file explorer open there.
#   3. In edit mode, start the `stargazer` MCP server on 127.0.0.1:8000, which
#      the proxy hands to each agent session in marimo's agent panel.
#   4. Start the reverse proxy on 0.0.0.0:8080 (the public port). Its startup
#      mounts the notebook's volume, and in edit mode it commits changes to it
#      on an interval.
#
# Pending edits are committed one last time before Knative idles the pod
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

# The proxy reads these to find, mount and name the notebook's volume.
export SG_NOTEBOOK_MODE="${MODE}" SG_NOTEBOOK_PATH="${NOTEBOOK_PATH}"

# A failed restore must not stop the pod from serving: the user just signs in
# to their agents again. Logged so it's diagnosable.
python -c "import sg_proxy; sg_proxy.restore_sign_ins()" \
  || echo "warning: could not restore agent sign-ins" >&2

# marimo (backgrounded) and the proxy (exec'd) inherit this cwd, which the
# proxy moves into the notebook's folder once it has mounted it.
cd "${WORKSPACE_DIR}"

# marimo's cwd, where its terminal and the agents it starts open: a volume
# notebook's folder, else /workspace, the root of a local notebook's file
# explorer.
WORKDIR="${WORKSPACE_DIR}"
[[ -n "${SG_NOTEBOOK_MANIFEST:-}" ]] && WORKDIR="$(dirname "${NOTEBOOK_PATH}")"

# `--watch` brings the agent's edits to the open notebook into the editor,
# which otherwise keeps its own copy and saves it back over them.
WATCH=()
[[ "${MODE}" == "edit" ]] && WATCH=(--watch)

start_marimo() {
  # A volume notebook's file isn't there until the proxy has mounted the
  # volume, which it does in its startup, after this script has exec'd it. A
  # mount that fails stops the proxy, so marimo is never started without one.
  local waited=0
  until [[ -z "${SG_NOTEBOOK_MANIFEST:-}" || -e "${NOTEBOOK_PATH}" ]]; do
    if (( waited >= 240 )); then
      echo "error: ${NOTEBOOK_PATH} did not appear within 2 minutes; the notebook's volume is not mounted, so marimo is not started" >&2
      return 1
    fi
    sleep 0.5
    waited=$((waited + 1))
  done

  # A header that doesn't pin Python gets conda-forge's newest in pixi's
  # sandbox, which marimo's own packages may not have builds for, and the
  # kernel never starts. A header saved before the pixi sandbox sources the
  # SDK only in `[tool.uv.sources]`, which pixi doesn't read, so its kernel
  # would install the SDK from PyPI. A failure here leaves the notebook as it
  # is, which is all a run-mode volume, mounted read-only, allows.
  python -c "import sys, sg_proxy; sg_proxy.pin_python(sys.argv[1]); sg_proxy.use_image_sdk(sys.argv[1])" "${NOTEBOOK_PATH}" \
    || echo "warning: could not check the notebook's header" >&2

  cd "${WORKDIR}"
  # `-q`: marimo's banner advertises its own port, 8081, which only the proxy
  # can reach.
  # marimo layers the launcher's version over the server and each kernel with
  # `uv run --with`, whose dependencies are unpinned. Resolved as of the image's
  # warm step (runtime/Dockerfile), they match the warmed layers, which uv would
  # otherwise download and install again at every start once any of them has a
  # newer release. pixi ignores the setting, so the notebook's own environment
  # resolves as it always does.
  UV_EXCLUDE_NEWER="$(cat /opt/uv-exclude-newer)" \
  exec marimo -q "${MODE}" --sandbox=pixi "${WATCH[@]}" "${NOTEBOOK_PATH}" \
    --port 8081 --host 127.0.0.1 --headless --no-token
}
# A subshell, so its `cd` and `exec` leave this script's alone.
( start_marimo ) &

# The agents' env has no project key (the proxy's `_agent_env`), so the server
# runs here, with the pod's whole env, where it can start runs in the owner's
# project. The panel is edit mode's only.
if [[ "${MODE}" == "edit" ]]; then
  /opt/mcp/bin/stargazer --http &
fi

# `--timeout-graceful-shutdown` is required for the shutdown flush to run, not
# just a tuning knob. On SIGTERM uvicorn drains open connections and in-flight
# background tasks BEFORE firing the FastAPI `lifespan` shutdown (the final commit
# of the notebook's edits). The proxy holds a long-lived task to the local marimo
# backend that does not drain on its own, so with the uvicorn default
# (`timeout_graceful_shutdown=None`) the drain waits forever and the flush never
# runs — verified empirically: the pod sat at "Waiting for background tasks to
# complete" indefinitely, even after the browser tab closed. A bounded timeout
# makes uvicorn cancel the lingering task and then still run `lifespan.shutdown`
# (it only skips the flush on a *second* SIGTERM / force-quit). 15s leaves ample
# room for the upload under the pod's 300s termination grace period.
exec uvicorn sg_proxy:asgi_app --host 0.0.0.0 --port 8080 \
  --timeout-graceful-shutdown 15
