# Dependency Analysis: claude-code-security-review

**Repo:** anthropics/claude-code-security-review
**Analyzed:** 2026-05-06
**Purpose:** An AI-powered security review GitHub Action using Claude to analyze code changes for security vulnerabilities. This action provides intelligent, context-aware security analysis for pull requests using Anthropic's Claude Code tool for deep semantic security analysis. See our blog post here for more d

---

## Languages & Runtimes
- Languages: node, python
- Runtime extras: bun
- Versions: none detected
- Base image: `not specified`

## System Packages
none detected

## Global JS Package Installs *(Dockerfile npm/pnpm/yarn/bun globals)*
none detected

## Dockerfile Python Installs *(`pip` / `pipx` in RUN blocks)*
none detected

## Dockerfile Go Installs *(`go install` in RUN blocks)*
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

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


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

## Inferred from Source *(tools/commands found in repo files)*
  - **CI toolchain (GitHub Actions)**: bun, checkout, node, npm, pip, pytest, python
  - **Python imports (not in manifest)**: anthropic, pytest, requests

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `pip` → `pip`
  - `python` → `python`
