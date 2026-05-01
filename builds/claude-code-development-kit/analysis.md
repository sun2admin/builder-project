# Dependency Analysis: claude-code-development-kit

**Repo:** peterkrueck/claude-code-development-kit
**Analyzed:** 2026-05-01
**Purpose:** A lightweight starter kit for Claude Code subscribers. Gives your project a solid foundation — documentation structure, code review automation, image tools, and sensible defaults — that you extend as you go.

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
- Inbound: none detected

## External Services *(source: source_scan)*
aistudio.google.com

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Credentials Required
  - SSH key required

## MCP Servers
none detected

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
No

## Firewall Required
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: curl, delta, git, go, jq, just, parallel, pip, task
  - **Python imports**: PIL, numpy

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `latest` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
