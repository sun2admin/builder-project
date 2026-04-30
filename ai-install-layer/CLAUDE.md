# Layer 2: ai-install-layer

**Published image**: `ghcr.io/sun2admin/ai-install-layer`
**Base**: `ghcr.io/sun2admin/base-ai-layer:latest`

## Tag Variants

| Tag | AI Tool | User Created |
|---|---|---|
| `:claude` | Claude Code CLI (`@anthropic-ai/claude-code`) | `claude` |
| `:gemini` | Gemini CLI (`@google/gemini-cli`) | `gemini` |

## Dockerfile Structure

Single Dockerfile with conditional ARG logic:

- `AI_TYPE=claude|gemini` — selects which npm package to install and which username to create
- `USERNAME=${AI_TYPE}` — user is named after the AI tool

**What gets set up per variant**:
- npm global install of AI CLI
- User created with `/bin/bash` shell
- `~/.claude` and `~/.ssh` dirs created, owned by user
- `/run/credentials` dir created (for bind-mounted secrets)
- `/commandhistory` dir for bash history persistence
- `/usr/local/share/npm-global` for npm global prefix (user-owned)
- `/opt/venv` ownership transferred to user
- Passwordless sudo for `init-firewall.sh` only (via `/etc/sudoers.d/`)
- System-wide env vars via `/etc/profile.d/ai-user.sh`: `NPM_CONFIG_PREFIX`, `PATH`, `SHELL`, `EDITOR`

## GitHub Actions

`build-and-push.yml` — matrix builds `:claude` and `:gemini` variants in parallel on push to main.

## Dependency

Rebuilding this layer requires rebuilding Layer 3 (plugins) to inherit the new base.
