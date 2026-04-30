# Layer 2: layer2-ai-install

**Published image**: `ghcr.io/sun2admin/layer2-ai-install`
**Base**: `ghcr.io/sun2admin/layer1-ai-depends:latest`

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

## Layer Directory Rule

Only modify the GitHub repo and GHCR image that exactly match this directory name (`layer2-ai-install` / `ghcr.io/sun2admin/layer2-ai-install`). Never modify a differently-named source repo unless explicitly instructed.

## GHCR Package Permissions (manual step after first image build)

After images are published, manually grant read access on this layer's GHCR package to all direct dependents:

- **This layer's package** → grant read access to all 8 plugin repos:
  - `claude-anthropic-base-plugins-container`
  - `claude-anthropic-coding-plugins-container`
  - `claude-anthropic-ext-plugins-container`
  - `claude-anthropic-all-plugins-container`
  - `claude-plugins-34e199d2`
  - `claude-plugins-3f889e47`
  - `claude-plugins-54ca621f`
  - `claude-plugins-a7f3d2e8`

Plugin repos do not need direct access to Layer 1 — all inherited layers are stored under this package's namespace in GHCR.
