# Dependency Analysis: claude-code-development-kit

**Repo:** peterkrueck/claude-code-development-kit
**Analyzed:** 2026-05-06
**Purpose:** A lightweight starter kit for Claude Code subscribers. Gives your project a solid foundation — documentation structure, code review automation, image tools, and sensible defaults — that you extend as you go.

---

## Languages & Runtimes
- Languages: shell
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
aistudio.google.com, github.com, raw.githubusercontent.com

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
  - **Tools/binaries (not in Dockerfile)**: added, afplay, allow, allow_entries, allow_json, always, aplay, ask, assets, auto, awk, base_add, base_del, basename, bash, cat, check_sensitive_content, chmod, claude, cleanup, clear, color, copy_file, cp, date, deleted, delta, deny, deny_entries, deny_json, dirname, existing, ffplay, file, files, find, gemini, git, grep, handle_file_conflict, head, hooks, hooks_json, https, input, jq, line_whitelisted, log_security_event, ls, macOS, matched_lines, mkdir, mktemp, needs_gemini_cli, needs_gemini_key, needs_rembg, next, notification_hooks, or, paplay, patterns, permissions, pip, play, play_sound_file, powershell, print, print_color, ps, pw-play, recommended, reference, review, review-on-stop, rm, safe_read, safe_read_conflict, safe_read_setup_mode, safe_read_yn, sanitized_input, scan_file_content, security, show_workflow_overview, sleep, sort, spec, spinner, spinstr, stat, tail, timestamp, total, touch, tr, uname, use, user_input, visual
  - **Python imports (not in manifest)**: PIL, numpy

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `awk` → `awk`
  - `basename` → `coreutils`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `cat` → `coreutils`
  - `chmod` → `coreutils`
  - `clear` → `ncurses-bin`
  - `cp` → `coreutils`
  - `date` → `coreutils`
  - `dirname` → `coreutils`
  - `find` → `findutils`
  - `git` → `git` (needs: libc6, libcurl3-gnutls, libexpat1, libpcre2-8-0, zlib1g)
  - `grep` → `grep` (needs: dpkg)
  - `head` → `coreutils`
  - `jq` → `jq` (needs: libjq1, libc6)
  - `ls` → `coreutils`
  - `mkdir` → `coreutils`
  - `mktemp` → `coreutils`
  - `pip` → `pip`
  - `ps` → `procps`
  - `rm` → `coreutils`
  - `sleep` → `coreutils`
  - `sort` → `coreutils`
  - `stat` → `coreutils`
  - `tail` → `coreutils`
  - `touch` → `coreutils`
  - `tr` → `coreutils`
  - `uname` → `coreutils`
