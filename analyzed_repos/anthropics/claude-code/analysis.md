# Dependency Analysis: claude-code

**Repo:** anthropics/claude-code
**Analyzed:** 2026-05-06
**Purpose:** Claude Code is an agentic coding tool that lives in your terminal, understands your codebase, and helps you code faster by executing routine tasks, explaining complex code, and handling git workflows -- all through natural language commands. Use it in your terminal, IDE, or tag @claude on Github.

---

## Languages & Runtimes
- Languages: node, python, shell
- Runtime extras: bun
- Versions: none detected
- Base image: `node:20`

## System Packages
aggregate, dnsutils, fzf, gh, git, gnupg2, iproute2, ipset, iptables, jq, less, man-db, nano, procps, sudo, unzip, vim, zsh

## Global JS Package Installs *(Dockerfile npm/pnpm/yarn/bun globals)*
@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

## Dockerfile Python Installs *(`pip` / `pipx` in RUN blocks)*
none detected

## Dockerfile Go Installs *(`go install` in RUN blocks)*
none detected

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

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - **post_start_chain**:
      - ○ baked/external (sudo): `/usr/local/bin/init-firewall.sh`
  - post_create_chain: none


## Credentials Required
  - API keys: ANTHROPIC_API_KEY, STATSIG_API_KEY
  - Tokens: GITHUB_TOKEN, ISSUE_OPENED_DISPATCH_TOKEN
  - SSH key required
  - Other: ISSUE_OPENED_DISPATCH_TARGET_REPO

## MCP Servers
none detected

## Claude Plugins
agent-sdk-dev, claude-opus-4-5-migration, code-review, commit-commands, explanatory-output-style, feature-dev, frontend-design, hookify, learning-output-style, plugin-dev, pr-review-toolkit, ralph-wiggum, security-guidance

## Browser / Test Tools
none detected

## GitHub API Usage
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: active, agent, arg, assistant, awk, bash, best, blue, can, cat, check_script, chmod, combines, completion_promise, content, content_size, create_sample, curl, cut, cyan, date, decision, denied, desc_length, dig, duration, end_time, error_count, errors, event_type, exit_code, fed, field, file_path, first_line, flag, found, frontmatter, gh_ranges, got, green, grep, haiku, hard, head, helper, hook_array_count, hook_count, hook_type, hooks, https, inherit, injection, input, ip, ips, iptables-save, iteration, join, length, ls, magenta, map, matched, matcher, max, max_iterations, maximum, minimum, missing, mkdir, must, mv, name, name_length, need, next, nothing, only, opus, output, over, perl, print, process, prompt, prompt_length, recommended, red, rm, runs, sed, self-referential, should, show_usage, skip_next, sonnet, start_time, started_at, steps, strict, tail, timeout, tool, tool_name, total_errors, tr, unless, unlimited, valid, validity, value, warning_count, warnings, wc, whoami, xargs, yellow
  - **Confirmed by Dockerfile**: aggregate, gh, ipset, iptables, jq
  - **CI toolchain (GitHub Actions)**: bun, checkout, claude-code, curl, date, events, floor, gh, github-script, head, http_code, issue_number, jq, metadata, now, repository, sed, tail, tonumber, tostring, triggered_by, value, workflow_run_id
  - **Python imports (not in manifest)**: hookify

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `aggregate` → `aggregate` (needs: libc6)
  - `awk` → `awk`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `cat` → `coreutils`
  - `chmod` → `coreutils`
  - `curl` → `curl` (needs: libc6, libcurl4, zlib1g)
  - `cut` → `coreutils`
  - `date` → `coreutils`
  - `dig` → `bind9-dnsutils`
  - `gh` → `gh` (needs: libc6)
  - `grep` → `grep` (needs: dpkg)
  - `head` → `coreutils`
  - `ip` → `iproute2`
  - `ipset` → `ipset` (needs: libc6, libipset13)
  - `iptables` → `iptables` (needs: libip4tc2, libip6tc2, libxtables12, netbase, libc6)
  - `join` → `coreutils`
  - `jq` → `jq` (needs: libjq1, libc6)
  - `ls` → `coreutils`
  - `mkdir` → `coreutils`
  - `mv` → `coreutils`
  - `perl` → `perl` (needs: perl-base, perl-modules-5.36, libperl5.36)
  - `rm` → `coreutils`
  - `sed` → `sed`
  - `tail` → `coreutils`
  - `timeout` → `coreutils`
  - `tr` → `coreutils`
  - `wc` → `coreutils`
  - `whoami` → `coreutils`
  - `xargs` → `findutils`
