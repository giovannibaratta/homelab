#!/bin/bash
#
# /usr/local/sbin/keepalived-nft-manager.sh
#
# This script manages nftables rules based on Keepalived state changes.
# It logs its actions and results to syslog with the tag "keepalived-nft".
#

# --- Configuration ---
LOG_TAG="keepalived-nft"
NFT_MASTER_RULES="/etc/nftables-vip-rules.master.nft"
NFT_BACKUP_RULES="/etc/nftables-vip-rules.backup.nft"
CHAIN_TO_FLUSH="ip custom_nat nat_prerouting"

# --- Functions ---

# Function to log messages to syslog
log_message() {
    local message="$1"
    logger -p daemon.info -t "${LOG_TAG}" "${message}"
    echo "${message}" # Also echo for journalctl visibility if keepalived captures stdout
}

# Function to execute a command and log the outcome
execute_command() {
    local cmd_string="$1"
    log_message "Executing: ${cmd_string}"

    # Execute the command, capturing both stdout and stderr
    output=$(eval "${cmd_string}" 2>&1)
    local status=$?

    if [ $status -ne 0 ]; then
        log_message "ERROR: Command failed with status ${status}. Output: ${output}"
        return 1
    else
        log_message "SUCCESS: Command executed. Output: ${output}"
        return 0
    fi
}

# --- Main Logic ---

STATE="$1" # The state is passed as the first argument from keepalived.conf

log_message "Script called with state: ${STATE}"

# We add "|| true" to the flush command to prevent the script from failing
# if the chain doesn't exist. This is expected behavior.
FLUSH_COMMAND="/usr/sbin/nft flush chain ${CHAIN_TO_FLUSH} || true"

case "$STATE" in
    "master")
        execute_command "${FLUSH_COMMAND}"
        execute_command "/usr/sbin/nft -f ${NFT_MASTER_RULES}"
        ;;
    "backup"|"fault"|"vrrp_stop")
        execute_command "${FLUSH_COMMAND}"
        execute_command "/usr/sbin/nft -f ${NFT_BACKUP_RULES}"
        ;;
    "startup")
        # At startup, we assume a safe "backup" state
        log_message "Keepalived daemon starting. Loading default (backup) rules."
        execute_command "${FLUSH_COMMAND}"
        execute_command "/usr/sbin/nft -f ${NFT_BACKUP_RULES}"
        ;;
    "shutdown")
        # When the daemon stops, we clean up the rules completely
        log_message "Keepalived daemon shutting down. Flushing rules."
        execute_command "${FLUSH_COMMAND}"
        ;;
    *)
        log_message "ERROR: Unknown state '${STATE}' received. Doing nothing."
        exit 1
        ;;
esac

# Exit with the status of the last command
exit $?