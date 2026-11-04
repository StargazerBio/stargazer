# The Stargazer image: the SDK, marimo and the notebook runtime, one image
# wherever a notebook runs. A hosted pod (Union, the devbox) runs it under
# Flyte's `fserve`, which replaces the entrypoint with the pod's launch command
# (`launch-notebook.sh <mode> <path>`) and passes the pod contract in its env.
# `docker run` gets the entrypoint below, which opens the notebooks locally.
# Built from the repo root: `docker build -f runtime/Dockerfile .`

# The agents for marimo's agent panel, pinned: Claude Code's Agent Client
# Protocol adapter, with the Claude Code binary its agent SDK ships, and
# OpenCode, a native binary that speaks the protocol itself. Node is copied
# into the image below.
FROM node:22.23.4-bookworm-slim AS agent
RUN npm install -g --omit=dev @agentclientprotocol/claude-agent-acp@0.99.1 \
        opencode-ai@1.19.5 \
    && npm cache clean --force

FROM ghcr.io/prefix-dev/pixi:0.83.0 AS pixi

FROM python:3.14-slim-bookworm

RUN apt-get update \
    && apt-get install -y build-essential ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash flyte

# pixi, which `marimo --sandbox=pixi` builds each notebook's environment
# with, from its header: conda packages (bioconda's tools among them) and PyPI
# ones. It also installs the MCP server's environment below. Newer than the
# pixi Flyte's image builder uses, which wrote pixi.lock (cli/lock_envs.py):
# marimo needs its `install --script`, and this version installs that lock
# as it is.
COPY --from=pixi /usr/local/bin/pixi /usr/local/bin/

# uv, which builds the runtime's venv below.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && install -m 755 /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/

# `claude` on PATH, for `/login` in marimo's terminal, is the binary the agent
# runs, so the two are one version; the pin only holds with auto-update off.
COPY --from=agent /usr/local/bin/node /usr/local/bin/
COPY --from=agent /usr/local/lib/node_modules/@agentclientprotocol \
    /usr/local/lib/node_modules/@agentclientprotocol
COPY --from=agent /usr/local/lib/node_modules/opencode-ai/bin/opencode.exe \
    /usr/local/bin/opencode
RUN ACP=/usr/local/lib/node_modules/@agentclientprotocol/claude-agent-acp \
    && ln -s "$ACP/dist/index.js" /usr/local/bin/claude-agent-acp \
    && ln -s "$(ls -d "$ACP"/node_modules/@anthropic-ai/claude-agent-sdk-linux-* \
        | grep -v musl)/claude" /usr/local/bin/claude \
    && claude --version && claude-agent-acp --help >/dev/null \
    && opencode --version

# The runtime's venv: the proxy's packages from the project's `runtime` group,
# `flyte` among them (hosted pods start under it, and the proxy stores
# notebooks with it), and the launcher marimo, pinned: a notebook's header
# lists `marimo` unpinned, and `--sandbox` layers this version over every
# kernel's venv. pydantic-ai-slim is what marimo's AI chat and completions run
# on in the server, with the OpenAI and Anthropic providers; marimo only
# brings it in its `recommended` extra. The range is that extra's for this
# marimo (plus the Anthropic provider), so the two move together. The
# SDK isn't installed here: each notebook's sandbox venv builds it from
# /stargazer.
COPY pyproject.toml /tmp/runtime/
RUN python -m venv /opt/venv \
    && uv pip install --no-cache --python /opt/venv/bin/python \
        --group /tmp/runtime/pyproject.toml:runtime marimo==0.25.1 \
        "pydantic-ai-slim[openai,anthropic]>=1.107,<3" \
    && rm -rf /tmp/runtime

# The proxy is a top-level module, not under `app/`: a hosted pod's code bundle
# unpacks an `app/` package into the working directory, which would shadow it.
COPY runtime/proxy.py /usr/local/lib/sg_proxy.py
COPY runtime/agent_redirect.html runtime/save_banner.html /usr/local/lib/
COPY runtime/launch-notebook.sh runtime/start-local.sh /usr/local/bin/
# Owned by the runtime user: each sandbox builds `stargazer-bio` from this tree
# and writes its egg-info here. pixi.lock is the MCP server's environment
# below and the one a notebook's own task images install (`core_image()`); a
# domain's task image installs its `env.py` header, from the lock beside it in
# src/. .dockerignore keeps the MCP server's environment, in .pixi/, out of
# the source layer of every task image a kernel builds from this tree.
COPY --chown=flyte:flyte pyproject.toml pixi.lock README.md .dockerignore /stargazer/
COPY --chown=flyte:flyte src/ /stargazer/src/

# The `stargazer` MCP server for the agent panel, which the launch script
# starts: pixi.lock's `mcp` environment, the SDK with the `mcp` extra, at the
# versions development runs, so it submits runs with the `flyte` the task
# images run. The runtime venv holds no SDK. Editable, so `init_flyte()`
# bundles a run from /stargazer, as a notebook's does; the chown hands the
# environment and the egg-info back to the runtime user.
RUN PIXI_CACHE_DIR=/tmp/pixi-cache pixi install --locked \
        --manifest-path /stargazer/pyproject.toml --environment mcp \
    && rm -rf /tmp/pixi-cache \
    && ln -s /stargazer/.pixi/envs/mcp /opt/mcp \
    && chown -R flyte:flyte /stargazer

# /workspace starts with the agent's context: Claude Code starts there and
# reads its AGENTS.md. The proxy records what's already there at startup as
# saved, so a hosted pod keeps this copy out of the user's store until they
# edit it. ~/.stargazer exists so a volume mounted there takes its ownership.
COPY --chown=flyte:flyte runtime/notebook_agent.md /workspace/AGENTS.md
COPY --chown=flyte:flyte runtime/marimo.toml /home/flyte/.config/marimo/marimo.toml
COPY --chown=flyte:flyte runtime/opencode.jsonc /home/flyte/.config/opencode/opencode.jsonc
RUN mkdir -p /home/flyte/.stargazer \
    && chown -R flyte:flyte /workspace /home/flyte/.stargazer /home/flyte/.config

# What a local /workspace starts with: the SDK's whole notebooks folder
# (templates and tutorials), without the package files: the notebooks
# are in its section directories, and the modules beside them (`ui.py`) aren't.
RUN mkdir /opt/workspace \
    && cp -r /stargazer/src/stargazer/notebooks /opt/workspace/ \
    && find /opt/workspace/notebooks -maxdepth 1 -name '*.py' -delete \
    && find /opt/workspace \( -name __init__.py -o -name __pycache__ \) \
        -prune -exec rm -rf {} + \
    && cp /workspace/AGENTS.md /opt/workspace/

# A locale the slim image has: marimo's terminal sets en_US.UTF-8 unless one
# is set, and bash warns that it doesn't exist. An environment links its
# packages from the caches below, which are in an image layer, where a hardlink
# costs a copy of the file, synced to disk: 20 s for a notebook on the core
# SDK, against 3 s with symlinks. pixi copies the conda packages' files
# instead, and symlinks the PyPI ones, as uv does.
ENV PATH="/opt/venv/bin:${PATH}" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONPATH="/usr/local/lib" \
    PIXI_CACHE_DIR="/opt/pixi-cache" \
    PIXI_NO_HARD_LINKS="true" \
    PIXI_NO_REF_LINKS="true" \
    UV_CACHE_DIR="/opt/uv-cache" \
    UV_LINK_MODE="symlink" \
    DISABLE_AUTOUPDATER="1"

RUN install -d -o flyte -g flyte /opt/pixi-cache /opt/uv-cache
USER flyte

# A warm cache, so a notebook's environment starts from local disk and only
# what a header adds comes from the network. These are the calls marimo makes:
# the server starts under a `--with marimo[lsp]` layer over the runtime venv,
# and a notebook's sandbox installs its header's environment with pixi, then
# starts the kernel under a `--with marimo` layer over it, both layers by uv
# through `pixi exec`. pixi keys a notebook's environment on its path, so the
# tutorials' are built where a hosted pod opens them, under /stargazer; any
# other path builds its own from the cache. The templates are only ever opened
# as copies, so only their packages are kept. Within this layer hardlinks
# cost nothing.
RUN export PIXI_NO_HARD_LINKS=false PIXI_NO_REF_LINKS=false \
        UV_LINK_MODE=hardlink \
    && UV="pixi exec --spec uv>=0.12 uv" \
    && VIRTUAL_ENV=/opt/venv $UV run -q --active --no-project \
        --python /opt/venv/bin/python --with "marimo[lsp]==0.25.1" \
        -- python -c 'import marimo' \
    && for nb in $(find /stargazer/src/stargazer/notebooks -mindepth 2 \
            -name '*.py' ! -name __init__.py); do \
        env="$(pixi install --script "$nb" 2>&1 \
            | sed -n "s/.*installed at '\(.*\)'\.$/\1/p")" \
        && [ -n "$env" ] \
        && case "$nb" in */templates/*) rm -rf "${env%/envs/*}"; continue ;; esac \
        && $UV run -q --no-project --python "$env/bin/python" \
            --with marimo==0.25.1 -- python -c 'import marimo, stargazer' \
        || exit 1; \
    done

# Not /workspace: a hosted pod's `fserve` unpacks its code bundle and writes
# its parameters file into the working directory, and the proxy saves
# everything in /workspace to the user's store. The launch script moves there.
WORKDIR /home/flyte

EXPOSE 8080
ENTRYPOINT ["start-local.sh"]
