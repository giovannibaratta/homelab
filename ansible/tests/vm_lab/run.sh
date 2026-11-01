#!/usr/bin/env bash

# Keep controller caches and generated Ansible files inside the repository.
set -euo pipefail

lab_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$lab_dir/../../.." && pwd)"

export PATH="$repo_dir/.venv-lab/bin:$PATH"
export XDG_CACHE_HOME="$repo_dir/ansible/.ansible/vm-lab/cache"
export ANSIBLE_HOME="$repo_dir/ansible/.ansible/vm-lab/ansible-home"

cd -- "$lab_dir"

exec "$repo_dir/.venv-lab/bin/molecule" "$@"
