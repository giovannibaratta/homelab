#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ANSIBLE_DIR}"

if [ -f "${ANSIBLE_DIR}/.venv/bin/activate" ]; then
    source "${ANSIBLE_DIR}/.venv/bin/activate"
fi

ansible-playbook -i inventory/home.yaml kubernetes_sigs.kubespray.facts "$@"
