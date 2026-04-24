---
name: Credential File Pattern for Dev Containers
description: Pattern for securely injecting secrets (SSH keys, GitHub PAT tokens) into containers via bind-mounted credential files and init scripts
type: project
---

## Pattern

Store secrets as files on the host under `~/Downloads/ClaudeFiles/Config/` and mount them readonly into `/run/credentials/` inside the container. A dedicated init script reads each credential and makes it available to the container environment.

## Current Credentials

| Host file | Container mount | Init script | Result |
|-----------|----------------|-------------|--------|
| `~/Downloads/ClaudeFiles/Config/gh_claude_ed25519` | `/run/credentials/gh_claude_ed25519` | `init-ssh.sh` | SSH key loaded into agent |
| `~/Downloads/ClaudeFiles/Config/gh_pat` | `/run/credentials/gh_pat` | `init-gh-token.sh` | `GH_TOKEN` written to `/home/claude/.profile` (chmod 600) |

## devcontainer.json mount entries

```json
"source=${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_claude_ed25519,target=/run/credentials/gh_claude_ed25519,type=bind,readonly",
"source=${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_pat,target=/run/credentials/gh_pat,type=bind,readonly"
```

## Making GH_TOKEN available

`init-gh-token.sh` writes to `/home/claude/.profile` (chmod 600) so `GH_TOKEN` is available in login shell sessions. Use `bash --login -c '...'` in `postAttachCommand` to ensure `.profile` is sourced. A sed-before-append pattern avoids duplicate entries on container restart:
```bash
sed -i '/^export GH_TOKEN=/d' /home/claude/.profile
echo "export GH_TOKEN=$(cat /run/credentials/gh_pat)" >> /home/claude/.profile
chmod 600 /home/claude/.profile
```

## Creating the host files

```bash
chmod 600 ~/Downloads/ClaudeFiles/Config/gh_pat
echo -n "ghp_xxxxx" > ~/Downloads/ClaudeFiles/Config/gh_pat
```

Use `-n` with echo to avoid a trailing newline in the token.

## Key rules

- Each credential gets its own init script — do not mix concerns into init-ssh.sh
- Scripts must be added to the Dockerfile `COPY` and `chmod +x` lines
- Scripts must be added to `postStartCommand` in devcontainer.json
- `/run/credentials/` must be created in the Dockerfile (`mkdir -p /run/credentials`)

## Why:
Keeps secrets off git, consistent with the SSH key pattern already established, and gives each credential an explicit, auditable init script.
