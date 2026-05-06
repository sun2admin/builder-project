# Dependency Analysis: awesome-claude-code

**Repo:** hesreallyhim/awesome-claude-code
**Analyzed:** 2026-05-06
**Purpose:** A curated list of awesome skills, hooks, slash-commands, agent orchestrators, applications, and plugins for Claude Code by Anthropic

---

## Languages & Runtimes
- Languages: python
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
  none detected

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
api.anthropic.com, api.github.com, author.example, awesome.re, docs.claude.com, example.com, formulae.brew.sh, github-readme-stats-fork-orpin.vercel.app, github-readme-stats-plus-theta.vercel.app, github.com, img.shields.io, pre-commit.com, www.anthropic.com

## Environment Variables
none detected

## Container Requirements
  standard (no special requirements)

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


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

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: after, allow_diff, backup, checks, cp, failure, git, keep_outputs, ls, make, mktemp, near, restore, restoring, rm, skipping
  - **CI toolchain (GitHub Actions)**: await, body, changes, checkout, comment_body, comment_id, console, const, contains, content, core, cp, env, event_type, first, git, github, github-api-usage-monitor, github-script, github_url, has_broken_links, https, id, is_github_repo, issue_number, jq, labels, maintainer, make, max_tokens, messages, model, owner, payload, pip, pr_body, pr_url, process, python, python3, reason, repo, repo_url, resource_name, rm, role, script, state, state_reason, success, system, tail, upload-artifact, uses
  - **Python imports (not in manifest)**: dotenv, github, pytest, requests, yaml

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `cp` → `coreutils`
  - `env` → `coreutils`
  - `git` → `git` (needs: libc6, libcurl3-gnutls, libexpat1, libpcre2-8-0, zlib1g)
  - `id` → `coreutils`
  - `jq` → `jq` (needs: libjq1, libc6)
  - `ls` → `coreutils`
  - `make` → `make`
  - `mktemp` → `coreutils`
  - `pip` → `pip`
  - `python` → `python`
  - `python3` → `python3` (needs: python3.11, libpython3-stdlib)
  - `rm` → `coreutils`
  - `script` → `bsdutils`
  - `tail` → `coreutils`
