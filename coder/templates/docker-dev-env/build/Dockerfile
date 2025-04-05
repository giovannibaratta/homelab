FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
        && apt-get install -y \
        curl \
        git \
        sudo \
        vim \
        wget \
        gpg \
        podman \
        fuse-overlayfs \
        slirp4netns \
        uidmap

# Install developer tools
RUN apt-get install -y \
        golang

RUN rm -rf /var/lib/apt/lists/*

ARG USER=coder

RUN useradd --groups sudo -m --shell /bin/bash ${USER} \
        && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
        && chmod 0440 /etc/sudoers.d/${USER}

# Install NVM
SHELL ["/bin/bash", "-c"]
ENV NVM_DIR /usr/local/nvm
ENV NODE_VERSION 22.14.0

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
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/corepack yarn install

USER ${USER}
WORKDIR /home/${USER}

# Podman configurations to run container as non-root user
RUN mkdir -p "/home/${USER}/.config/containers" && \
    mkdir -p "/home/${USER}/.local/share/containers/storage" && \
    echo '[storage]' > /home/${USER}/.config/containers/storage.conf && \
    echo 'driver = "overlay"' >> /home/${USER}/.config/containers/storage.conf && \
    echo "graphroot = \"/home/${USER}/.local/share/containers/storage\"" >> /home/${USER}/.config/containers/storage.conf

