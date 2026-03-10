FROM ubuntu

RUN apt-get update \
    && apt-get install -y \
    sudo \
    jq \
    vim \
    curl \
    git \
    nano \
    nodejs \
    npm \
    bwa \
    wget \
    unzip \
    python3 \
    python3-pip \
    openjdk-17-jre-headless \
    zsh \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Install GATK
ENV GATK_VERSION=4.6.1.0
RUN wget https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip \
    && unzip gatk-${GATK_VERSION}.zip \
    && mv gatk-${GATK_VERSION} /opt/gatk \
    && rm gatk-${GATK_VERSION}.zip \
    && ln -s /opt/gatk/gatk /usr/local/bin/gatk

ENV PATH="/opt/gatk:${PATH}"

# Install Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Install OpenCode
RUN npm install -g opencode-ai

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Convenience
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes

ARG USER=coder
RUN useradd --groups sudo --no-create-home --shell /bin/zsh ${USER} \
    && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
    && chmod 0440 /etc/sudoers.d/${USER}
USER ${USER}
WORKDIR /home/${USER}

ENTRYPOINT ["/bin/zsh"]
