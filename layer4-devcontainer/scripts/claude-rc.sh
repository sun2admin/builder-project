#!/bin/bash
# Custom rcfile for the integrated terminal in Layer 4 devcontainers.
# Referenced by .vscode/tasks.json (auto-open) and devcontainer.json
# customizations.vscode.settings.terminal.integrated.profiles.linux.claude-bash
# (default profile for every Ctrl+` terminal).

[ -f ~/.bashrc ] && source ~/.bashrc
[ -f ~/.profile ] && source ~/.profile

alias myclaude='cd $(cat ~/live-project 2>/dev/null || echo ~) && claude --dangerously-skip-permissions'
