#!/usr/bin/env bash
# The image's entrypoint for `docker run`, where there's no dashboard to launch
# notebooks from. A hosted pod never runs this: Flyte replaces the entrypoint.
#
# Runs are local, their records in SQLite for the TUI. The config is in
# ~/.flyte, Flyte's last lookup, so it stays out of the file explorer and a
# directory mounted at /workspace doesn't hide it.
#
# The notebooks are copied into /workspace and marimo opens on the first
# tutorial. The launch script starts marimo in /workspace, the root of its file
# explorer, so every other notebook is in the sidebar and opens from there.
# Edits land in a mounted directory, and each notebook runs in a sandbox built
# from its own header. A file already there is the user's and is left alone
# (`cp -n`).
set -euo pipefail

[ -f "$HOME/.flyte/config.yaml" ] \
  || flyte create config --local-persistence -o "$HOME/.flyte/config.yaml" >/dev/null
cp -rn /opt/workspace/. /workspace/
echo "Stargazer notebooks: http://localhost:8080"
exec launch-notebook.sh edit /workspace/notebooks/tutorials/assets.py
