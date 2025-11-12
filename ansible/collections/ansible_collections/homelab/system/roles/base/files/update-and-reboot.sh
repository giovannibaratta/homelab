#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Function to display usage information ---
usage() {
  echo "Usage: $0 [--validate-health HOST1,HOST2,...]"
  exit 1
}

# --- Default variables ---
VALIDATE_HOSTS=""

# --- Parse Command-Line Arguments ---
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --validate-health)
      VALIDATE_HOSTS="$2"
      shift
      ;;
    *)
      usage
      ;;
  esac
  shift
done

# --- 1. Perform System Updates ---
echo "Starting system update..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get autoremove -y
apt-get autoclean -y
echo "System update completed."

# --- 2. Health Checks (if specified) ---
if [[ -n "$VALIDATE_HOSTS" ]]; then
  echo "Performing health checks..."
  # Convert comma-separated string to an array
  IFS=',' read -r -a HOST_ARRAY <<< "$VALIDATE_HOSTS"

  for host in "${HOST_ARRAY[@]}"; do
    echo -n "Pinging ${host}... "
    if ping -c 1 "${host}" &> /dev/null; then
      echo "OK"
    else
      echo "FAILED"
      echo "Error: Host ${host} is not reachable. Aborting reboot."
      exit 1
    fi
  done
  echo "All hosts are healthy."
fi

# --- 3. Check for Running Ansible Playbooks ---
echo "Checking for running ansible-playbook processes..."
if pgrep -f "ansible-playbook" > /dev/null; then
  echo "Error: An ansible-playbook process is currently running. Aborting reboot."
  exit 1
else
  echo "No running ansible-playbook processes found."
fi

# --- 4. Reboot the System ---
echo "All checks passed. Rebooting now..."
reboot

exit 0