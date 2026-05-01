# Dependency Analysis: claude-code-security-review

**Repo:** anthropics/claude-code-security-review
**Analyzed:** 2026-05-01
**Purpose:** An AI-powered security review GitHub Action using Claude to analyze code changes for security vulnerabilities. This action provides intelligent, context-aware security analysis for pull requests using Anthropic's Claude Code tool for deep semantic security analysis. See our blog post here for more d

---

## Languages & Runtimes
- Languages: node, python
- Runtime extras: bun
- Versions: none detected
- Base image: `not specified`

## System Packages
none detected

## Libraries
  none detected

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
none detected

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Credentials Required
  - API keys: ANTHROPIC_API_KEY, CLAUDE_API_KEY
  - Tokens: GITHUB_TOKEN

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
  - **Python imports**: anthropic, claudecode, pytest, requests

## Suggested Stack
| Setting | Value |
|---|---|
| Base image (layer1 variant) | `latest` |
| Dockerfile FROM | `python:latest` |
| AI CLI | `claude` |
| Plugin layer | (query dynamically at build time) |
