#!/bin/bash

# Docker logs script for OliveTin
# Usage: docker-logs.sh --container <container_name> [--tail] [--grep <pattern>]

CONTAINER_NAME=""
TAIL_50=false
GREP_FILTER=""

# Validation functions
validate_container_name() {
    local name="$1"

    # Check if empty
    if [ -z "$name" ]; then
        echo "Error: Container name cannot be empty"
        return 1
    fi

    # Check length (Docker container names: 1-253 characters)
    if [ ${#name} -gt 253 ]; then
        echo "Error: Container name too long (max 253 characters)"
        return 1
    fi

    # Check for valid characters only: alphanumeric, hyphens, underscores
    if [[ ! "$name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "Error: Container name can only contain alphanumeric characters, hyphens, and underscores"
        return 1
    fi

    return 0
}

validate_grep_filter() {
    local filter="$1"

    # If empty, that's fine (optional parameter)
    if [ -z "$filter" ]; then
        return 0
    fi

    # Check length (max 100 characters)
    if [ ${#filter} -gt 100 ]; then
        echo "Error: Grep filter too long (max 100 characters)"
        return 1
    fi

    # Check for valid characters only: alphanumeric and hyphens
    if [[ ! "$filter" =~ ^[a-zA-Z0-9-]+$ ]]; then
        echo "Error: Grep filter can only contain alphanumeric characters and hyphens"
        return 1
    fi

    return 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --tail)
            TAIL_50=true
            shift
            ;;
        --grep)
            GREP_FILTER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Validate inputs
if ! validate_container_name "$CONTAINER_NAME"; then
    exit 1
fi

if ! validate_grep_filter "$GREP_FILTER"; then
    exit 1
fi

# Build docker logs command with proper quoting
if [ "$TAIL_50" = true ]; then
    if [ -n "$GREP_FILTER" ] && [ "$GREP_FILTER" != "" ]; then
        DOCKER_HOST=docker-socket-proxy-ro:2375 docker logs --tail 50 "$CONTAINER_NAME" 2>&1 | grep "$GREP_FILTER"
    else
        DOCKER_HOST=docker-socket-proxy-ro:2375 docker logs --tail 50 "$CONTAINER_NAME" 2>&1
    fi
else
    if [ -n "$GREP_FILTER" ] && [ "$GREP_FILTER" != "" ]; then
        DOCKER_HOST=docker-socket-proxy-ro:2375 docker logs "$CONTAINER_NAME" 2>&1 | grep "$GREP_FILTER"
    else
        DOCKER_HOST=docker-socket-proxy-ro:2375 docker logs "$CONTAINER_NAME" 2>&1
    fi
fi