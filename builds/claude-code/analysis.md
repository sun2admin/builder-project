# Dependency Analysis: claude-code

**Repo:** anthropics/claude-code
**Analyzed:** 2026-04-30
**Purpose:** Claude Code is an agentic coding tool that lives in your terminal, understands your codebase, and helps you code faster by executing routine tasks, explaining complex code, and handling git workflows -- all through natural language commands. Use it in your terminal, IDE, or tag @claude on Github.

---

## Languages & Runtimes
- Languages: shell
- Runtime extras: bun
- Versions: none detected
- Base image: `node:20`

## System Packages
aggregate, dnsutils, fzf, gh, git, gnupg2, iproute2, ipset, iptables, jq, less, man-db, nano, procps, sudo, unzip, vim, zsh

## Libraries
  none detected

## Ports
- Inbound: none detected

## External Services *(source: init-firewall.sh)*
api.anthropic.com, marketplace.visualstudio.com, registry.npmjs.org, sentry.io, statsig.anthropic.com, statsig.com, update.code.visualstudio.com, vscode.blob.core.windows.net

## Environment Variables
CLAUDE_CONFIG_DIR, DEVCONTAINER, EDITOR, NODE_OPTIONS, NPM_CONFIG_PREFIX, PATH, POWERLEVEL9K_DISABLE_GITSTATUS, SHELL, TZ, VISUAL

## Container Requirements
  - Docker caps: NET_ADMIN, NET_RAW
  - User: node
  - postStartCommand: `sudo /usr/local/bin/init-firewall.sh`
  - Volume: `claude-code-bashhistory-${devcontainerId}` → `/commandhistory`
  - Volume: `claude-code-config-${devcontainerId}` → `/home/node/.claude`
  - ENV: `NODE_OPTIONS`
  - ENV: `CLAUDE_CONFIG_DIR`
  - ENV: `POWERLEVEL9K_DISABLE_GITSTATUS`

## Credentials Required
  - API keys: ANTHROPIC_API_KEY, STATSIG_API_KEY
  - Tokens: GITHUB_TOKEN, ISSUE_OPENED_DISPATCH_TOKEN
  - SSH key required
  - Other: ANTHROPIC_API_KEY, GITHUB_TOKEN, ISSUE_OPENED_DISPATCH_TARGET_REPO, ISSUE_OPENED_DISPATCH_TOKEN, STATSIG_API_KEY

## MCP Servers
none detected

## Claude Plugins
agent-sdk-dev, claude-opus-4-5-migration, code-review, commit-commands, explanatory-output-style, feature-dev, frontend-design, hookify, learning-output-style, plugin-dev, pr-review-toolkit, ralph-wiggum, security-guidance

## Browser / Test Tools
none detected

## GitHub API Usage
No

## Firewall Required
Yes — NET_ADMIN/NET_RAW capabilities needed

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries**: curl, gh, git, go, gradle, java, jq, just, python, sudo, xargs
  - **Python imports**: hookify

## Suggested Stack
| Setting | Value |
|---|---|
| Base image | `latest` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
