# Dependency Analysis: builder-project

**Repo:** sun2admin/builder-project
**Analyzed:** 2026-04-30
**Purpose:** Example Layer 4 Claude project demonstrating the multi-project workspace architecture.

---

## Languages & Runtimes
- Languages: shell
- Runtime extras: none detected
- Versions: none detected
- Base image: `node:22-slim`

## System Packages
gh, ipykernel, jupyterlab, numpy, pandas, pdfplumber, pymupdf, pypdf, python3-pip, reportlab, weasyprint

## Libraries
  none detected

## Ports
- Inbound: none detected

## External Services *(source: init-firewall.sh)*
api.anthropic.com, claude.ai, marketplace.visualstudio.com, registry.npmjs.org, sentry.io, statsig.anthropic.com, statsig.com, update.code.visualstudio.com, vscode.blob.core.windows.net

## Environment Variables
DEVCONTAINER, PATH, PLAYWRIGHT_BROWSERS_PATH, PLAYWRIGHT_CHROMIUM_SANDBOX, TZ

## Container Requirements
  standard (no special requirements)

## Credentials Required
  - Tokens: GITHUB_TOKEN
  - SSH key required
  - Other: GITHUB_TOKEN

## MCP Servers
github

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
Yes

## Firewall Required
Yes — NET_ADMIN/NET_RAW capabilities needed

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries**: curl, docker, gh, git, jq, playwright, python, rsync, ssh-add, ssh-agent, xargs

## Suggested Stack
| Setting | Value |
|---|---|
| Base image | `latest` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
