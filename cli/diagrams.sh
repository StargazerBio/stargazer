#!/usr/bin/env bash
# Draws import graphs with pydeps into diagrams/ (gitignored). With no arguments
# it draws the standard set. Given module files, it draws one diagram per module
# instead: the module and everything it imports, directly or not. Settings
# shared by every diagram are [tool.pydeps] in pyproject.toml.
#
#   cli/diagrams.sh                            # sdk.svg, sdk-modules.svg
#   cli/diagrams.sh src/stargazer/server.py    # stargazer.server.svg
set -euo pipefail

cd "$(dirname "$0")/.."

# The editable install finds stargazer through an import hook that pydeps'
# module finder can't follow. Without src on the path, a diagram would silently
# leave out every SDK module it imports.
export PYTHONPATH=src

mkdir -p diagrams

# draw <path> <diagram name> [pydeps option...]
# pydeps writes the graph as dot source and pygraphviz renders it with the
# Graphviz its wheel bundles: pydeps' own rendering needs a system `dot`.
draw() {
    # Absolute, since pydeps changes directory while it works.
    local dot="$PWD/diagrams/$2.dot" svg="diagrams/$2.svg"
    uv run --group diagrams pydeps "$1" --no-output --dot-output "$dot" "${@:3}"
    uv run --group diagrams python -c \
        'import sys, pygraphviz; pygraphviz.AGraph(sys.argv[1]).draw(sys.argv[2], prog="dot")' \
        "$dot" "$svg"
    rm "$dot"
    echo "$svg"
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
        draw "$path" "${name//\//.}" --only stargazer "$(basename "$path")"
    done
else
    draw src/stargazer sdk --max-module-depth 2
    draw src/stargazer sdk-modules
fi
