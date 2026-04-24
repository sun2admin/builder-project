---
name: Use bash not zsh in devcontainers
description: Prefer bash over zsh in Linux devcontainers — zsh adds complexity with no benefit for non-interactive use
type: feedback
---

Use bash as the default shell in devcontainers, not zsh.

**Why:** zsh must be explicitly installed (not in node:20-slim), requires zsh-in-docker for a usable setup, and adds .zshenv/.zshrc complexity. Claude Code does not require zsh — it supports all common shells equally. bash is pre-installed, uses standard /etc/skel files (.bashrc, .bash_profile), and is the Linux standard.

**How to apply:** useradd with -s /bin/bash. Set terminal.integrated.defaultProfile.linux to "bash" in devcontainer.json. No need to install zsh or zsh-in-docker in the image or user-setup feature.
