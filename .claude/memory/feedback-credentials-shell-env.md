---
name: Shell env vars for credentials in devcontainers
description: How to securely expose PAT tokens to all processes including non-interactive subprocesses in a bash-based devcontainer
type: feedback
---

Use ~/.profile (chmod 600) for credential env vars, not /etc/environment or .bashrc.

**Why:** /etc/environment is world-readable — any user can see secrets stored there. .bashrc is only sourced for interactive non-login shells, so Claude's MCP subprocesses don't inherit the vars. ~/.profile is sourced for login shells and is private to the user.

**How to apply:** In init scripts that write PAT tokens, write to ~/.profile with chmod 600. In postAttachCommand, use `bash --login -c '...'` so .profile is sourced before the process starts. Use sed-before-append pattern to prevent duplicate entries on container restart:
```
sed -i '/^export GH_TOKEN=/d' ~/.profile
echo "export GH_TOKEN=$PAT" >> ~/.profile
```