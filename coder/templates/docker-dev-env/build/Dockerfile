FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
        && apt-get install -y \
        curl \
        git \
        golang \
        sudo \
        vim \
        wget \
        gpg \
        podman \
        fuse-overlayfs \
        slirp4netns \
        uidmap \
        && rm -rf /var/lib/apt/lists/*

ARG USER=coder
RUN useradd --groups sudo -m --shell /bin/bash ${USER} \
        && echo "${USER} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USER} \
        && chmod 0440 /etc/sudoers.d/${USER}

# Podman configurations to run container as non-root user
RUN mkdir -p "/home/${USER}/.config/containers" && \
    mkdir -p "/home/${USER}/.local/share/containers/storage" && \
    chown -R ${USER}:${USER} "/home/${USER}/.local" && \
	  chown -R ${USER}:${USER} "/home/${USER}/.config" && \
    echo '[storage]' > /home/${USER}/.config/containers/storage.conf && \
    echo 'driver = "overlay"' >> /home/${USER}/.config/containers/storage.conf && \
    echo "graphroot = \"/home/${USER}/.local/share/containers/storage\"" >> /home/${USER}/.config/containers/storage.conf

USER ${USER}

WORKDIR /home/${USER}