FROM ubuntu

ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y \
    curl \
    wget \
    unzip \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install GATK
ENV GATK_VERSION=4.6.1.0
RUN wget https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip \
    && unzip gatk-${GATK_VERSION}.zip \
    && mv gatk-${GATK_VERSION} /opt/gatk \
    && rm gatk-${GATK_VERSION}.zip \
    && ln -s /opt/gatk/gatk /usr/local/bin/gatk

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Copy project
WORKDIR /stargazer
COPY . .
RUN uv sync

ENTRYPOINT ["claude"]
