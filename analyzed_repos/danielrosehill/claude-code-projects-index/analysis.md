# Dependency Analysis: claude-code-projects-index

**Repo:** danielrosehill/claude-code-projects-index
**Analyzed:** 2026-05-01
**Purpose:** A curated collection of Claude Code projects, agent workspace blueprints, and related resources — organized by use case. Most patterns here adapt to other agentic AI CLIs and frameworks.

---

## Languages & Runtimes
- Languages: node, shell
- Runtime extras: none detected
- Versions: none detected
- Base image: `not specified`

## System Packages
none detected

## Libraries
  - **node**: astro

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
anthropic.com, claude.com, danielrosehill.com, dsrholdings.cloud

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
  - **Tools/binaries (not in Dockerfile)**: git, python3

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `latest` |
| Dockerfile FROM | `node:lts` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
