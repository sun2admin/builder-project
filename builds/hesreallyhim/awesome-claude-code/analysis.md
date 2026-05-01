# Dependency Analysis: awesome-claude-code

**Repo:** hesreallyhim/awesome-claude-code
**Analyzed:** 2026-05-01
**Purpose:** A curated list of awesome skills, hooks, slash-commands, agent orchestrators, applications, and plugins for Claude Code by Anthropic

---

## Languages & Runtimes
- Languages: python
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
api.anthropic.com, claude.com

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Credentials Required
  - API keys: ANTHROPIC_API_KEY
  - Tokens: GITHUB_TOKEN, SC_DISPATCH_TOKEN
  - SSH key required
  - Other: ACC_OPS, AWESOME_CC_PAT_PUBLIC_REPO, SC_DISPATCH_URL

## MCP Servers
none detected

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
Yes

## Firewall Required
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: git, make, pip, python, python3
  - **Python imports**: dotenv, github, pytest, requests, yaml

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `latest` |
| Dockerfile FROM | `python:3` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
