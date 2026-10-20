# The one human-runnable image: `stargazer`, the hosted notebook image
# (`notebook_app_img_recipe` in `app/per_notebook.py`) as a `docker run`.
# marimo edits behind the same proxy, so the dropdown terminal (Ctrl+`) has
# Claude Code in it, and `/stargazer` is the SDK that each notebook's
# `[tool.uv.sources]` resolves in its sandbox venv. The two recipes share no
# code: tests/unit/test_dockerfile.py checks that this one has the proxy's pip
# packages and the files it reads beside itself, and the tool versions are kept
# in step by hand. They differ on purpose only in multi-arch downloads and in
# having no Flyte-injected runtime or platform login.
FROM python:3.13-slim-bookworm

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
    && curl -fsSL https://claude.ai/install.sh | HOME=/opt/claude-cli bash -s 2.1.153 \
    && chmod -R a+rX /opt/claude-cli \
    && ln -s /opt/claude-cli/.local/bin/claude /usr/local/bin/claude

# The launcher marimo is pinned: notebooks don't list marimo in their PEP 723
# headers, `--sandbox` injects this version into each kernel venv. `flyte` is
# what the proxy stores notebooks with.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        "flyte>=2.0.3" marimo==0.23.6 "fastapi>=0.115" "uvicorn>=0.34" \
        "httpx>=0.27" "websockets>=12" "pyjwt[crypto]>=2.8,<3"

COPY app/proxy.py /usr/local/lib/sg_proxy.py
COPY app/terminal_overlay.html app/save_banner.html /usr/local/lib/
COPY app/launch-notebook.sh /usr/local/bin/
# Owned by the runtime user: each sandbox builds `stargazer` from this tree
# and writes its egg-info here.
COPY --chown=flyte:flyte pyproject.toml README.md /stargazer/
COPY --chown=flyte:flyte src/ /stargazer/src/
COPY --chown=flyte:flyte app/ /stargazer/app/

# ~/.stargazer exists so a volume mounted there takes its ownership from it.
RUN mkdir -p /workspace /snapshots /home/flyte/.stargazer \
    && chown -R flyte:flyte /workspace /snapshots /home/flyte/.stargazer

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/usr/local/lib" \
    UV_LINK_MODE="copy" \
    DISABLE_AUTOUPDATER="1"

# Runs are local, their records in SQLite for the TUI. The config lands in the
# notebook's working directory.
USER flyte
WORKDIR /workspace
RUN flyte create config --local-persistence

EXPOSE 8080
ENTRYPOINT ["launch-notebook.sh", "edit", "/stargazer/src/stargazer/notebooks/tutorials/assets.py"]
