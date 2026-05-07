#!/bin/bash
set -e

GH_PAT_MOUNT=/run/credentials/gh_pat

if [ -f "$GH_PAT_MOUNT" ]; then
    PAT=$(cat "$GH_PAT_MOUNT")
    # Write to ~/.profile — sourced for login shells, readable only by claude
    touch /home/claude/.profile
    chmod 600 /home/claude/.profile
    sed -i '/^export GH_TOKEN=/d' /home/claude/.profile
    sed -i '/^export GITHUB_PERSONAL_ACCESS_TOKEN=/d' /home/claude/.profile
    echo "export GH_TOKEN=$PAT" >> /home/claude/.profile
    echo "export GITHUB_PERSONAL_ACCESS_TOKEN=$PAT" >> /home/claude/.profile
else
    echo "WARNING: GitHub PAT not found at $GH_PAT_MOUNT"
fi
