FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

ARG USER=coder

# Add Podman 5.x repository and pin the version
RUN apt-get update && apt-get install -y curl gpg ca-certificates \
        && curl -fsSL http://downloadcontent.opensuse.org/repositories/home:/alvistack/xUbuntu_24.04/Release.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/home_alvistack.gpg \
        && echo "deb http://downloadcontent.opensuse.org/repositories/home:/alvistack/xUbuntu_24.04/ /" > /etc/apt/sources.list.d/home:alvistack.list \
        && printf "Package: podman\nPin: version 5.*\nPin-Priority: 1001\n" > /etc/apt/preferences.d/podman-pin

# python3-yaml required by Podman compose
# gettext-base for installing envsubst
# openssh-client for signing commits

RUN apt-get update \
        && apt-get install -y \
        apt-transport-https \
        git \
        sudo \
        vim \
        wget \
        podman \
        podman-docker \
        aardvark-dns \
        passt \
        python3-setuptools \
        fuse-overlayfs \
        slirp4netns \
        uidmap \
        jq \
        tmux \
        python3-yaml \
        gettext-base \
        openssh-client

RUN touch /etc/containers/nodocker \
        && curl -fsSL -o /tmp/netavark.gz https://github.com/containers/netavark/releases/download/v1.16.1/netavark.gz \
        && gunzip /tmp/netavark.gz \
        && mkdir -p /usr/libexec/podman \
        && mv /tmp/netavark /usr/libexec/podman/netavark \
        && chmod +x /usr/libexec/podman/netavark

# Create user after uidmap is installed to ensure subuid/subgid files are handled correctly
RUN useradd --groups sudo -m --shell /bin/bash ${USER} \
        && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
        && chmod 0440 /etc/sudoers.d/${USER} \
        && groupadd -f containers \
        && usermod -aG containers ${USER}

# Manually ensure subuid/subgid entries exist for rootless Podman
RUN echo "${USER}:100000:65536" >> /etc/subuid && \
        echo "${USER}:100000:65536" >> /etc/subgid

# Use podman-compose instead of docker-compose. Docker compose requires a socket to be
# available, creating the socket in the container is not so easy.
RUN curl -o /usr/local/bin/podman-compose \
        https://raw.githubusercontent.com/containers/podman-compose/main/podman_compose.py && \
        chmod +x /usr/local/bin/podman-compose

RUN apt-get install -y python3-yaml \
        python3-dotenv

ENV PODMAN_COMPOSE_PROVIDER=/usr/local/bin/podman-compose

RUN echo 'unqualified-search-registries = ["docker.io"]' > /etc/containers/registries.conf

RUN cat <<EOF >> /etc/containers/registries.conf.d/99-dockerhub.conf
[[registry]]
prefix = ""
insecure = false
blocked = false
location = "docker.io"
EOF

# Podman configurations to run container as non-root user
RUN mkdir -p /ephermeral/podman/storage /ephermeral/podman/run && \
        chown -R ${USER}:containers /ephermeral && \
        chmod -R 775 /ephermeral && \
        printf "[storage]\ndriver = \"overlay\"\ngraphroot = \"/ephermeral/podman/storage\"\nrunroot = \"/ephermeral/podman/run\"\n" > /etc/containers/storage.conf

# Install developer tools
RUN apt-get install -y \
        golang \
        openjdk-17-jre

# Install NVM
SHELL ["/bin/bash", "-c"]
ENV NVM_DIR=/usr/local/nvm
ENV NODE_VERSION=22.14.0

RUN mkdir -p ${NVM_DIR}

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.2/install.sh | bash

# install node and npm
RUN source $NVM_DIR/nvm.sh \
        && nvm install $NODE_VERSION \
        && nvm alias default $NODE_VERSION \
        && nvm use default

ENV NODE_PATH=$NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/corepack yarn install

RUN mkdir -p /workspace && \
        chown -R ${USER}:${USER} /workspace

USER ${USER}

RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g corepack
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g @google/gemini-cli
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g @anthropic-ai/claude-code

WORKDIR /workspace
