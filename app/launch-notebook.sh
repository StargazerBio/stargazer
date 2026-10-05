#!/usr/bin/env bash
# Launch script baked into the notebook-app image at
# /usr/local/bin/launch-notebook.sh. Invoked as the per-notebook
# AppEnvironment's args:
#
#     /usr/local/bin/launch-notebook.sh <mode> <notebook_path>
#
# Three things happen on startup:
#
#   1. Hydrate: copy the owner's notebooks from the workspace store into
#      /workspace and their own snapshots into /snapshots (flat, one file per
#      notebook), via the proxy module's `hydrate()`. A new user, or a deploy
#      without a store, starts with empty dirs. The session then cd's into
#      /workspace so marimo and the proxy's dropdown terminal both work there.
#   2. Start marimo on 127.0.0.1:8081 in sandbox mode (notebook's PEP 723
#      header drives the venv).
#   3. Start the owner-gated reverse proxy on 0.0.0.0:8080 (the public port).
#      It also writes edited notebooks back to the store every few seconds.
#
# Pending workspace edits are saved one last time before Knative idles the pod
# by the proxy's FastAPI shutdown hook, which fires on SIGTERM. For that to
# work the proxy (uvicorn) must be the process Flyte's `fserve` wrapper signals.
# `fserve` is PID 1; it runs this script via `Popen(cmd, shell=True)` and on
# SIGTERM forwards the signal to that ONE direct child only (it does not signal
# the whole tree). So uvicorn must end up as `fserve`'s direct child:
#   - The AppEnvironment args prepend `exec` (see app/per_notebook.py), so the
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
# (exec'd) both inherit this cwd, so the dropdown terminal — and any `claude`
# launched in it — open here.
cd "${WORKSPACE_DIR}" 2>/dev/null || true

marimo "${MODE}" --sandbox "${NOTEBOOK_PATH}" \
  --port 8081 --host 127.0.0.1 --headless --no-token &

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
