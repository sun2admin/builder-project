#!/bin/bash
set -e

KEY_MOUNT=/run/credentials/gh_claude_ed25519
KEY_COPY=/tmp/gh_claude_ed25519
AGENT_SOCK=/home/claude/.ssh/agent.sock

# Copy mounted key and lock down permissions (ssh-add requires 600)
cp "$KEY_MOUNT" "$KEY_COPY"
chmod 600 "$KEY_COPY"

# Start ssh-agent at fixed socket path
rm -f "$AGENT_SOCK"
ssh-agent -a "$AGENT_SOCK"

# Load key into agent
SSH_AUTH_SOCK="$AGENT_SOCK" ssh-add "$KEY_COPY"

# Remove temp copy
rm -f "$KEY_COPY"

# Add github.com to known_hosts if not already present (ignore failures)
ssh-keyscan -H github.com >> /home/claude/.ssh/known_hosts 2>/dev/null || true
