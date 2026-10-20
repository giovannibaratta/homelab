#!/bin/bash

# Build-time only. Usage: bash install-tools.sh ARCH GODOT_VERSION SDK_VERSION RUNTIME_VERSION
# Installs .NET into /opt/dotnet and Godot into /opt/godot, with launchers on PATH.
# Requires curl, jq, sha512sum, tar and unzip (provided by the image).
# Downloads are verified before extraction; temporary files are removed on exit.

set -euo pipefail

target_arch=${1:?Missing target architecture}
godot_version=${2:?Missing Godot version}
sdk_version=${3:?Missing .NET SDK version}
runtime_version=${4:?Missing .NET runtime version}

case "$target_arch" in
    amd64) dotnet_arch=x64; godot_arch=x86_64 ;;
    arm64) dotnet_arch=arm64; godot_arch=arm64 ;;
    *) echo "Unsupported architecture: $target_arch" >&2; exit 1 ;;
esac

temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
cd "$temporary"

# Keep the existing toolchain record: one verified download per JSON object.
record_download() {
    jq -n --arg tool "$1" --arg version "$2" --arg url "$3" --arg sha512 "$4" \
        '$ARGS.named' >> toolchain.jsonl
}

install_dotnet() {
    local channel=$1 kind=$2 version=$3
    local url checksum

    curl -fsSL --retry 3 \
        "https://builds.dotnet.microsoft.com/dotnet/release-metadata/$channel/releases.json" \
        -o releases.json
    jq -er --arg kind "$kind" --arg version "$version" --arg rid "linux-$dotnet_arch" '
        .releases[] | .[$kind] | select(.version == $version)
        | .files[] | select(.rid == $rid and (.url | endswith(".tar.gz")))
        | [.url, .hash] | @tsv
    ' releases.json > asset.tsv
    test "$(wc -l < asset.tsv)" -eq 1
    read -r url checksum < asset.tsv

    curl -fsSL --retry 3 "$url" -o "$kind.tar.gz"
    printf '%s  %s\n' "$checksum" "$kind.tar.gz" | sha512sum --check --strict
    tar -xzf "$kind.tar.gz" -C /opt/dotnet
    record_download "$kind" "$version" "$url" "$checksum"
}

# Install the SDK and the additional runtime required by Godot's net8.0 assemblies.
mkdir -p /opt/dotnet
install_dotnet 10.0 sdk "$sdk_version"
install_dotnet 8.0 runtime "$runtime_version"
ln -s /opt/dotnet/dotnet /usr/local/bin/dotnet

# Install the Godot .NET editor using its published archive checksum.
archive="Godot_v${godot_version}-stable_mono_linux_${godot_arch}.zip"
base="https://github.com/godotengine/godot-builds/releases/download/${godot_version}-stable"
curl -fsSL --retry 3 "$base/$archive" -o "$archive"
curl -fsSL --retry 3 "$base/SHA512-SUMS.txt" -o SHA512-SUMS.txt
awk -v archive="$archive" '$2 == archive || $2 == "*" archive { print }' \
    SHA512-SUMS.txt > godot.sha512
test "$(wc -l < godot.sha512)" -eq 1
sha512sum --check --strict godot.sha512
mkdir -p /opt/godot
unzip -q "$archive" -d /opt/godot
binary="/opt/godot/${archive%.zip}/Godot_v${godot_version}-stable_mono_linux.${godot_arch}"
test -x "$binary"
ln -s "$binary" /usr/local/bin/godot-mono

read -r checksum _ < godot.sha512
record_download godot "$godot_version" "$base/$archive" "$checksum"
jq -s '.' toolchain.jsonl > /opt/gforfun-toolchain.json
