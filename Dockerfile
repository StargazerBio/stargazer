FROM ubuntu AS base

ENV PATH="/root/.local/bin:/usr/local/bin:/opt/conda/bin:${PATH}"

# System packages
RUN apt-get update \
    && apt-get install -y curl wget unzip \
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

# uv + Claude Code
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
RUN curl -fsSL https://claude.ai/install.sh | bash

# --- Quickstart target ---
FROM base AS quickstart
WORKDIR /stargazer
COPY . .
RUN uv sync
ENTRYPOINT ["claude"]

# --- Dev target ---
FROM base AS dev
RUN apt-get update \
    && apt-get install -y \
    sudo jq vim git nano python3 python3-pip zsh tmux \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS + OpenCode
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g opencode-ai

# Convenience
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes

ARG USER=coder
RUN useradd --groups sudo --no-create-home --shell /bin/zsh ${USER} \
    && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
    && chmod 0440 /etc/sudoers.d/${USER}
USER ${USER}
WORKDIR /home/${USER}
ENTRYPOINT ["/bin/zsh"]
