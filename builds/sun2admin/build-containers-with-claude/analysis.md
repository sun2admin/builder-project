# Dependency Analysis: build-containers-with-claude

**Repo:** sun2admin/build-containers-with-claude
**Analyzed:** 2026-04-30
**Purpose:** Layer 4 Part 1 devcontainer config for building containers with Claude Code

---

## Languages & Runtimes
- Languages: shell
- Runtime extras: none detected
- Versions: none detected
- Base image: `not specified`

## System Packages
none detected

## Libraries
  none detected

## Ports
- Inbound: 8888

## External Services *(source: source_scan)*
github.com

## Environment Variables
CLAUDE_CONFIG_DIR, NODE_OPTIONS, SSH_AUTH_SOCK

## Container Requirements
  - Docker caps: NET_ADMIN, NET_RAW
  - User: claude
  - postStartCommand: `sudo /usr/local/bin/init-firewall.sh && /workspace/.devcontainer/scripts/init-ssh.sh && /workspace/.devcontainer/scripts/init-gh-token.sh && /workspace/.devcontainer/scripts/init-github-mcp.sh && /workspace/.devcontainer/scripts/load-projects.sh -live sun2admin/builder-project`
  - Volume: `claude-code-bashhistory-${devcontainerId}` → `/commandhistory`
  - Volume: `claude-code-config-${devcontainerId}` → `/home/claude/.claude`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/SharedFiles` → `/home/claude/data`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_claude_ed25519` → `/run/credentials/gh_claude_ed25519`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_pat` → `/run/credentials/gh_pat`
  - ENV: `NODE_OPTIONS`
  - ENV: `CLAUDE_CONFIG_DIR`
  - ENV: `SSH_AUTH_SOCK`

## Credentials Required
  - Tokens: GITHUB_TOKEN
  - SSH key required
  - Other: GITHUB_TOKEN

## MCP Servers
none detected

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
No

## Firewall Required
Yes — NET_ADMIN/NET_RAW capabilities needed

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries**: git, ssh-add, ssh-agent

## Suggested Stack
| Setting | Value |
|---|---|
| Base image | `latest` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
