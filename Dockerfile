FROM ubuntu AS base

ENV VIRTUAL_ENV="/stargazer/.venv"
ENV PATH="/stargazer/.venv/bin:/usr/local/bin:/opt/conda/bin:/home/ubuntu/.local/bin:${PATH}"

# System packages
RUN apt-get update \
    && apt-get install -y curl wget unzip git \
    && rm -rf /var/lib/apt/lists/*

# Mamba (miniforge)
RUN curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh -o /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh

# Bioinformatics tools via bioconda
RUN mamba install -y -c bioconda -c conda-forge \
    bwa \
    bwa-mem2 \
    samtools \
    gatk4 \
    && mamba clean -afy

# uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && install -m 755 /root/.local/bin/uv /usr/local/bin/uv \
    && install -m 755 /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /stargazer
COPY --chown=ubuntu:ubuntu pyproject.toml uv.lock ./
COPY --chown=ubuntu:ubuntu src/ src/
RUN uv sync && chown -R ubuntu:ubuntu /stargazer

# --- Note target (Marimo notebook UI) ---
# Same image serves local `docker run` and hosted production via
# `flyte.serve(note_env)` (note_env consumes this image as its base).
FROM base AS note
USER ubuntu
RUN flyte create config --local-persistence
ENTRYPOINT ["marimo", "edit", "src/stargazer/notebooks/byod.py", \
    "--port", "8080", "--host", "0.0.0.0", "--headless", "--no-token"]

# --- Chat target (agentic interface to the MCP server) ---
# End-user image: Claude Code + OpenCode pre-wired against the Stargazer
# MCP server. Not a contributor dev shell.
FROM base AS chat

# Node.js LTS + OpenCode
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g opencode-ai

# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && install -m 755 /root/.local/bin/claude /usr/local/bin/claude

COPY --chown=ubuntu:ubuntu .mcp.json .mcp.json
COPY --chown=ubuntu:ubuntu .claude/settings.json .claude/settings.json

USER ubuntu
ENTRYPOINT ["claude"]
