FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

ARG USER=coder

# Add Podman 5.x repository and pin the version
RUN apt-get update && apt-get install -y curl gpg ca-certificates \
        && curl -fsSL http://downloadcontent.opensuse.org/repositories/home:/alvistack/xUbuntu_24.04/Release.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/home_alvistack.gpg \
        && echo "deb http://downloadcontent.opensuse.org/repositories/home:/alvistack/xUbuntu_24.04/ /" > /etc/apt/sources.list.d/home:alvistack.list \
        && printf "Package: *\nPin: release l=home:alvistack\nPin-Priority: 1001\n" > /etc/apt/preferences.d/podman-pin

# python3-yaml required by Podman compose
# gettext-base for installing envsubst
# openssh-client for signing commits

RUN apt-get update \
        && apt-get install -y \
        apt-transport-https \
        git \
        libcap2-bin \
        vim \
        wget \
        podman \
        podman-docker \
        python3-setuptools \
        slirp4netns \
        uidmap \
        jq \
        tmux \
        python3-yaml \
        python3-dotenv \
        gettext-base \
        openssh-client \
        zsh \
        ripgrep \
        bubblewrap

# AppArmor policy belongs to the node's coder_workspace_security Ansible role.

# 1. Install latest Netavark v2.1.0 & Aardvark-DNS v2.1.0 release binaries for Podman 6.x rootless network stack
# 2. Install upstream passt/pasta package:
#    Ubuntu 24.04 ships an outdated passt (Feb 2024, 0.0~git20240220) that has a protocol
#    return-path bug on NATed/forwarded Netavark bridge networks (e.g. podman-compose).
#    This bug caused outbound WAN HTTPS data transfers to stall immediately after TLS ClientHello.
#    Installing upstream passt (0.0~git20260728.f8df3f1) resolves the bridge WAN egress issue.
RUN touch /etc/containers/nodocker \
        && mkdir -p /usr/libexec/podman /usr/lib/podman \
        && curl -fsSL -o /tmp/netavark.gz https://github.com/containers/netavark/releases/download/v2.1.0/netavark.gz \
        && gunzip /tmp/netavark.gz \
        && chmod +x /tmp/netavark \
        && cp /tmp/netavark /usr/libexec/podman/netavark \
        && cp /tmp/netavark /usr/lib/podman/netavark \
        && rm /tmp/netavark \
        && curl -fsSL -o /tmp/aardvark.gz https://github.com/containers/aardvark-dns/releases/download/v2.1.0/aardvark-dns.gz \
        && gunzip /tmp/aardvark.gz \
        && chmod +x /tmp/aardvark \
        && cp /tmp/aardvark /usr/libexec/podman/aardvark-dns \
        && cp /tmp/aardvark /usr/lib/podman/aardvark-dns \
        && rm /tmp/aardvark \
        && curl -fsSL -o /tmp/passt.deb http://ftp.debian.org/debian/pool/main/p/passt/passt_0.0~git20260728.f8df3f1-1_amd64.deb \
        && dpkg -i /tmp/passt.deb \
        && rm /tmp/passt.deb

# Create user after uidmap is installed to ensure subuid/subgid files are handled correctly
RUN useradd --uid 1001 --user-group -K SUB_UID_COUNT=0 -K SUB_GID_COUNT=0 -m --shell /bin/zsh ${USER} \
        && groupadd -f containers \
        && usermod -aG containers ${USER}

# Preserve BOTH previous adjacent coder ranges and their container-ID mapping.
# Replace the image's allocation files to remove Ubuntu's overlapping range.
# Do not shrink to 65536 IDs: existing storage may use the upper half.
RUN printf '%s:100000:131072\n' "${USER}" > /etc/subuid && \
        printf '%s:100000:131072\n' "${USER}" > /etc/subgid

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
RUN mkdir -p /ephemeral/podman/storage && \
        chown -R ${USER}:containers /ephemeral && \
        chmod -R 775 /ephemeral && \
        printf "[storage]\ndriver = \"overlay\"\ngraphroot = \"/ephemeral/podman/storage\"\nrunroot = \"/tmp/podman-run-1001\"\n" > /etc/containers/storage.conf

# Use kernel rootless overlay: no host /dev/fuse or runtime socket is exposed.
# Nested containers inherit the node's outer AppArmor profile. "unconfined"
# here suppresses an OCI request to load/switch an INNER AppArmor profile;
# it cannot remove the already-enforced outer profile (no change_profile rule).
# Kubernetes owns the outer cgroup; no writable host cgroup mount is needed.
# Keep the Dockerfile self-contained: the build runner stages only this file.
RUN printf '%s\n' \
        '[containers]' \
        'apparmor_profile = "unconfined"' \
        'cgroups = "disabled"' \
        'keyring = false' \
        'log_driver = "k8s-file"' \
        '' \
        '[engine]' \
        'cgroup_manager = "cgroupfs"' \
        'events_logger = "file"' > /etc/containers/containers.conf

# Install developer tools
RUN apt-get update && apt-get install -y \
        golang \
        openjdk-17-jre

# Install NVM
SHELL ["/bin/bash", "-c"]
ENV NVM_DIR=/usr/local/nvm
ENV NODE_VERSION=22.23.0

RUN mkdir -p ${NVM_DIR}

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh | bash

# install node and npm
RUN bash -c "source $NVM_DIR/nvm.sh \
        && nvm install $NODE_VERSION \
        && nvm alias default $NODE_VERSION \
        && nvm use default"

ENV NODE_PATH=$NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/corepack enable

# Change ownership of NVM_DIR so coder user can write to it to install/run npm packages
RUN chown -R ${USER}:${USER} ${NVM_DIR}

RUN mkdir -p /workspace && \
        chown -R ${USER}:${USER} /workspace

# Keep this after all apt/package installation, which can restore setuid bits.
# Helpers stay UID 1001 and acquire only their individual mapping capability.
# No general-purpose setuid/sudo path to outer-container root remains.
RUN find /usr -xdev -type f -perm /6000 -exec chmod a-s {} + \
        && setcap cap_setuid=ep /usr/bin/newuidmap \
        && setcap cap_setgid=ep /usr/bin/newgidmap \
        && getcap /usr/bin/newuidmap /usr/bin/newgidmap

USER ${USER}

# Install Oh My Zsh and zsh-autosuggestions
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended && \
        git clone https://github.com/zsh-users/zsh-autosuggestions /home/${USER}/.oh-my-zsh/custom/plugins/zsh-autosuggestions && \
        sed -i 's/plugins=(git)/plugins=(git zsh-autosuggestions)/' /home/${USER}/.zshrc && \
        chown -R ${USER}:${USER} /home/${USER}/.oh-my-zsh /home/${USER}/.zshrc

RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g corepack
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g @anthropic-ai/claude-code
# The pinned Coder module installs only codex; the npm package also supplies
# codex-code-mode-host, which is required for Codex tool execution.
RUN $NVM_DIR/versions/node/v$NODE_VERSION/bin/npm install -g @openai/codex

RUN curl -fsSL https://antigravity.google/cli/install.sh | bash

WORKDIR /workspace
