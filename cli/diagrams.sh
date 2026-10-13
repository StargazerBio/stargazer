#!/usr/bin/env bash
# Draws import graphs with pydeps into diagrams/ (gitignored). With no arguments
# it draws the standard set. Given module files, it draws one diagram per module
# instead: the module and everything it imports, directly or not. Settings
# shared by every diagram are [tool.pydeps] in pyproject.toml.
#
#   cli/diagrams.sh                            # sdk.svg, sdk-modules.svg, app.svg
#   cli/diagrams.sh src/stargazer/server.py    # stargazer.server.svg
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v dot >/dev/null; then
    echo "pydeps draws with graphviz's dot: brew install graphviz, or apt install graphviz" >&2
    exit 1
fi

# The editable install finds stargazer through an import hook that pydeps'
# module finder can't follow. Without src on the path, a diagram of app/ would
# silently leave out every SDK module it imports.
export PYTHONPATH=src

mkdir -p diagrams

# draw <path> <diagram name> [pydeps option...]
draw() {
    uv run pydeps "$1" -o "diagrams/$2.svg" "${@:3}"
    echo "diagrams/$2.svg"
}

if [ $# -gt 0 ]; then
    for path in "$@"; do
        # Given a directory, pydeps draws the whole top-level package around it.
        if [ ! -f "$path" ]; then
            echo "$path: pass a module file; the default set covers whole packages" >&2
            exit 1
        fi
        name="${path#src/}"
        name="${name%.py}"
        # pydeps names the module's own node after its file, which the
        # [tool.pydeps] `only` would filter out.
        draw "$path" "${name//\//.}" --only stargazer app "$(basename "$path")"
    done
else
    draw src/stargazer sdk --max-module-depth 2
    draw src/stargazer sdk-modules
    draw app app
fi
