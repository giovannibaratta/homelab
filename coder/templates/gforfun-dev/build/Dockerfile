# Inherit the Kubernetes workspace toolchain; add only GForFun-specific tools.
ARG BASE_IMAGE=ghcr.io/giovannibaratta/base-dev:latest
FROM ${BASE_IMAGE}

USER root

ARG TARGETARCH
ARG GODOT_VERSION=4.7.2
ARG DOTNET_VERSION=10.0.402
# Godot's net8.0 assemblies need a .NET 8 runtime as well as the newer SDK.
ARG DOTNET_RUNTIME_VERSION=8.0.21

RUN apt-get update && apt-get install -y --no-install-recommends \
    git-lfs rsync unzip zip procps file xz-utils libicu74 libssl3t64 zlib1g libstdc++6 \
    libgl1 libgl1-mesa-dri libvulkan1 libx11-6 libxcursor1 libxinerama1 \
    libxi6 libxrandr2 libxrender1 libfontconfig1 libasound2t64 libpulse0 \
    && rm -rf /var/lib/apt/lists/*

COPY install-tools.sh /tmp/install-tools.sh

RUN bash /tmp/install-tools.sh "$TARGETARCH" "$GODOT_VERSION" "$DOTNET_VERSION" "$DOTNET_RUNTIME_VERSION" \
    && rm /tmp/install-tools.sh \
    && ! ldd /usr/local/bin/godot-mono | grep 'not found' \
    && godot-mono --headless --version \
    && dotnet --list-sdks && dotnet --list-runtimes

# The shared base already creates coder; keep the PVC ownership contract.
RUN test "$(id -u coder):$(id -g coder)" = 1001:1001 \
    && install -d -o coder -g coder /workspace/gforfun \
    && git lfs install --system

# Package installation can restore setuid/setgid bits removed by the base image.
RUN find /usr -xdev -type f -perm /6000 -exec chmod a-s {} +

ENV HOME=/home/coder DOTNET_ROOT=/opt/dotnet PATH=/opt/dotnet:${PATH} \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

# Keep package caches disposable. Project build directories stay in /workspace.
# pip also follows XDG_CACHE_HOME; Python uses its normal in-project bytecode cache.
ENV XDG_CACHE_HOME=/ephemeral/cache \
    NUGET_PACKAGES=/ephemeral/nuget/packages NUGET_HTTP_CACHE_PATH=/ephemeral/nuget/http \
    DOTNET_CLI_HOME=/ephemeral/dotnet npm_config_cache=/ephemeral/npm

USER coder
WORKDIR /workspace/gforfun

RUN codex --version \
    && test -x "$(command -v codex-code-mode-host)" && bwrap --version

CMD ["sleep", "infinity"]
