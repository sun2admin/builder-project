# build-with-claude

A devcontainer project for building and managing GitHub repos using Claude Code.

## Architecture

This repo uses a 4-layer container architecture (inherited from base images):

- **Layer 1 (base-ai-layer)**: `ghcr.io/sun2admin/base-ai-layer:latest` — system packages, dev tools, Python, graphics libs, Playwright browsers
- **Layer 2 (ai-install-layer)**: `ghcr.io/sun2admin/ai-install-layer:claude` — Claude Code CLI + claude user + env setup
- **Layer 3 (plugins)**: `ghcr.io/sun2admin/claude-plugins-a7f3d2e8:latest` — pre-baked Claude Code plugins
- **Layer 4 (project)**: This repo (build-with-claude) references Layer 3 image in devcontainer.json
- **Container user**: `claude` (bash shell)

## Init Scripts

Run at container start via `postStartCommand`:

| Script | Purpose |
|---|---|
| `init-firewall.sh` | Configures iptables egress rules (runs as sudo) |
| `init-ssh.sh` | Loads SSH key from `/run/credentials/gh_claude_ed25519` into ssh-agent |
| `init-gh-token.sh` | Reads PAT from `/run/credentials/gh_pat`, writes to `~/.profile` (chmod 600) |
| `init-github-mcp.sh` | Copies arch-appropriate `github-mcp-server` binary to `~/.local/bin/` |

## Credentials

Secrets are injected via bind-mounted files at `/run/credentials/`:
- `gh_claude_ed25519` — SSH private key for GitHub
- `gh_pat` — GitHub Personal Access Token

The PAT is written to `/home/claude/.profile` with `chmod 600` so only the `claude` user can read it. It is **not** stored in `/etc/environment` (world-readable) or `.bashrc` (not sourced by subprocesses).

`postAttachCommand` uses `bash --login` to ensure `.profile` is sourced before Claude starts, making the PAT available to Claude and its MCP subprocesses.

## Shell

The container uses **bash** (not zsh). Claude Code does not require zsh. Bash is pre-installed in the base image and avoids the complexity of zsh-in-docker setup.

## MCP

`claude/.mcp.json` configures the GitHub MCP server, which exposes GitHub API as tools to Claude. The binary is committed to `scripts/bin/` and updated weekly via GitHub Actions (`update-github-mcp.yml`).

## GitHub Actions

`update-github-mcp.yml` — checks for new `github-mcp-server` releases weekly, verifies checksums, commits updated binaries, and opens a PR.