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

# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && install -m 755 /root/.local/bin/claude /usr/local/bin/claude

WORKDIR /stargazer
COPY --chown=ubuntu:ubuntu pyproject.toml uv.lock ./
COPY --chown=ubuntu:ubuntu .mcp.json .mcp.json
COPY --chown=ubuntu:ubuntu .claude/settings.json .claude/settings.json

# --- Note target (production notebook) ---
# Tighter image for researchers comfortable with notebooks and light CLI.
# Entrypoint launches marimo in edit mode on localhost.
# Same image serves local use and hosted production.
FROM base AS note
COPY --chown=ubuntu:ubuntu src/ src/
RUN uv sync && chown -R ubuntu:ubuntu /stargazer
USER ubuntu
RUN flyte create config --local-persistence
ENTRYPOINT ["marimo", "edit", "src/stargazer/notebooks/getting_started.py", \
    "--port", "8080", "--host", "0.0.0.0", "--headless", "--no-token"]

# --- Chat target (agentic dev harness) ---
# For contributors who mount the repo from the host and work in editable mode.
# Ships with Claude Code, OpenCode, and standard dev tooling.
FROM base AS chat
RUN apt-get update \
    && apt-get install -y \
    sudo jq vim git nano python3 python3-pip tmux \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS + OpenCode
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g opencode-ai

# Convenience
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes

RUN chown ubuntu:ubuntu /stargazer
USER ubuntu

# uv sync then launch Claude Code.
ENTRYPOINT ["bash", "-c", "uv sync --group dev && exec claude"]
