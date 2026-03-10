FROM ubuntu

RUN apt-get update \
    && apt-get install -y \
    sudo \
    jq \
    curl \
    git \
    nano \
    bwa \
    wget \
    unzip \
    python3 \
    python3-pip \
    python3.10-venv \
    openjdk-17-jre-headless \
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

# Convenience
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes

ARG USER=coder
RUN useradd --groups sudo --no-create-home --shell /bin/bash ${USER} \
    && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
    && chmod 0440 /etc/sudoers.d/${USER}
USER ${USER}
WORKDIR /home/${USER}

ENTRYPOINT ["/bin/bash"]
