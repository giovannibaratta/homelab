FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
        && apt-get install -y \
        apt-transport-https \
        curl \
        git \
        sudo \
        vim \
        wget \
        gpg \
        podman \
        podman-docker \
        python3-setuptools \
        fuse-overlayfs \
        slirp4netns \
        uidmap

# Use podman-compose instead of docker-compose. Docker compose requires a socket to be
# available, creating the socket in the container is not so easy.
RUN curl -o /usr/local/bin/podman-compose \
        https://raw.githubusercontent.com/containers/podman-compose/main/podman_compose.py && \
        chmod +x /usr/local/bin/podman-compose

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
ENV CONTAINERS_ROOT_DIR=/ephermeral/podman/containers
ENV CONTAINERS_STORAGE_CONF=${CONTAINERS_ROOT_DIR}/storage.conf
ENV CONTAINERS_GRAPHROOT=${CONTAINERS_ROOT_DIR}/storage

RUN mkdir -p "${CONTAINERS_ROOT_DIR}" && \
        mkdir -p "${CONTAINERS_GRAPHROOT}" && \
        echo '[storage]' > ${CONTAINERS_STORAGE_CONF} && \
        echo 'driver = "overlay"' >> ${CONTAINERS_STORAGE_CONF} && \
        echo "graphroot = \"${CONTAINERS_GRAPHROOT}\"" >> ${CONTAINERS_STORAGE_CONF} && \
        chown -R ${USER}:${USER} "${CONTAINERS_ROOT_DIR}"

# Install developer tools
RUN apt-get install -y \
        golang \
        openjdk-17-jre

RUN rm -rf /var/lib/apt/lists/*

ARG USER=coder

RUN useradd --groups sudo -m --shell /bin/bash ${USER} \
        && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
        && chmod 0440 /etc/sudoers.d/${USER}

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

RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g corepack
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g @google/gemini-cli
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/corepack yarn install

RUN mkdir -p /workspace && \
        chown -R ${USER}:${USER} /workspace

USER ${USER}
WORKDIR /workspace
