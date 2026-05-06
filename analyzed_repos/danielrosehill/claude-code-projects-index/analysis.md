# Dependency Analysis: claude-code-projects-index

**Repo:** danielrosehill/claude-code-projects-index
**Analyzed:** 2026-05-06
**Purpose:** A curated collection of Claude Code projects, agent workspace blueprints, and related resources — organized by use case. Most patterns here adapt to other agentic AI CLIs and frameworks.

---

## Languages & Runtimes
- Languages: node, python, shell
- Runtime extras: none detected
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
  - **node**: astro

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
anthropic.com, claude.com, danielrosehill.com, github.com, img.shields.io

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


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

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: basename, bash, git, ln, name, python3

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `basename` → `coreutils`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `git` → `git` (needs: libc6, libcurl3-gnutls, libexpat1, libpcre2-8-0, zlib1g)
  - `ln` → `coreutils`
  - `python3` → `python3` (needs: python3.11, libpython3-stdlib)
