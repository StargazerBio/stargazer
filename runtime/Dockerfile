# The Stargazer image: the SDK, marimo and the notebook runtime, one image
# wherever a notebook runs. A hosted pod (Union, the devbox) runs it under
# Flyte's `fserve`, which replaces the entrypoint with the pod's launch command
# (`launch-notebook.sh <mode> <path>`) and passes the pod contract in its env.
# `docker run` gets the entrypoint below, which opens the notebooks locally.
# Built from the repo root: `docker build -f runtime/Dockerfile .`
FROM python:3.14-slim-bookworm

RUN apt-get update \
    && apt-get install -y build-essential ca-certificates curl git bzip2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash flyte

# micromamba + the bioinformatics tools (same set as gatk_env), reachable by
# subprocess from inside each notebook's sandbox venv.
RUN case "$(uname -m)" in x86_64) MM=linux-64 ;; aarch64) MM=linux-aarch64 ;; esac \
    && curl -Ls "https://micro.mamba.pm/api/micromamba/${MM}/latest" \
        | tar -xj -C /usr/local/bin --strip-components=1 bin/micromamba \
    && micromamba create -p /opt/conda -y -c bioconda -c conda-forge \
        gatk4 samtools bwa bwa-mem2 \
    && micromamba clean -a -y \
    && ln -s /opt/conda/bin/gatk /opt/conda/bin/java /opt/conda/bin/samtools \
        /opt/conda/bin/bwa /opt/conda/bin/bwa-mem2* /usr/local/bin/

# uv, which `marimo --sandbox` uses to build per-notebook venvs.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && install -m 755 /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/

# Claude Code, pinned and installed under a fixed HOME so it sits at stable
# paths whichever user runs it; the pin only holds with auto-update off.
RUN mkdir -p /opt/claude-cli \
    && curl -fsSL https://claude.ai/install.sh | HOME=/opt/claude-cli bash -s 2.1.304 \
    && chmod -R a+rX /opt/claude-cli \
    && ln -s /opt/claude-cli/.local/bin/claude /usr/local/bin/claude

# The runtime's venv: the proxy's packages from the project's `runtime` group,
# `flyte` among them (hosted pods start under it, and the proxy stores
# notebooks with it), and the launcher marimo, pinned: notebooks don't list
# marimo in their headers, and `--sandbox` puts this version into every
# kernel's venv. The SDK isn't installed here: each notebook's sandbox venv
# builds it from /stargazer.
COPY pyproject.toml /tmp/runtime/
RUN python -m venv /opt/venv \
    && uv pip install --no-cache --python /opt/venv/bin/python \
        --group /tmp/runtime/pyproject.toml:runtime marimo==0.23.6 \
    && rm -rf /tmp/runtime

# The proxy is a top-level module, not under `app/`: a hosted pod's code bundle
# unpacks an `app/` package into the working directory, which would shadow it.
COPY runtime/proxy.py /usr/local/lib/sg_proxy.py
COPY runtime/terminal_overlay.html runtime/save_banner.html /usr/local/lib/
COPY runtime/launch-notebook.sh runtime/start-local.sh /usr/local/bin/
# Owned by the runtime user: each sandbox builds `stargazer-bio` from this tree
# and writes its egg-info here. The lock is there for the task images a kernel
# builds (`with_uv_project`): Union's builder skips a uv project layer without
# one.
COPY --chown=flyte:flyte pyproject.toml uv.lock README.md /stargazer/
COPY --chown=flyte:flyte src/ /stargazer/src/

# /workspace starts with the terminal agent's context: Claude Code starts there
# and reads its AGENTS.md. The proxy records what's already there at startup as
# saved, so a hosted pod keeps this copy out of the user's store until they
# edit it. ~/.stargazer exists so a volume mounted there takes its ownership.
COPY --chown=flyte:flyte runtime/notebook_agent.md /workspace/AGENTS.md
RUN mkdir -p /home/flyte/.stargazer \
    && chown -R flyte:flyte /workspace /home/flyte/.stargazer

# What a local /workspace starts with: the SDK's whole notebooks folder
# (templates, tutorials, workflows), without the package files: the notebooks
# are in its section directories, and the modules beside them (`ui.py`) aren't.
RUN mkdir /opt/workspace \
    && cp -r /stargazer/src/stargazer/notebooks /opt/workspace/ \
    && find /opt/workspace/notebooks -maxdepth 1 -name '*.py' -delete \
    && find /opt/workspace \( -name __init__.py -o -name __pycache__ \) \
        -prune -exec rm -rf {} + \
    && cp /workspace/AGENTS.md /opt/workspace/

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/usr/local/lib" \
    UV_LINK_MODE="copy" \
    DISABLE_AUTOUPDATER="1"

# Not /workspace: a hosted pod's `fserve` unpacks its code bundle and writes
# its parameters file into the working directory, and the proxy saves
# everything in /workspace to the user's store. The launch script moves there.
USER flyte
WORKDIR /home/flyte

EXPOSE 8080
ENTRYPOINT ["start-local.sh"]
