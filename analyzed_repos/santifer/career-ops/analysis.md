# Dependency Analysis: career-ops

**Repo:** santifer/career-ops
**Analyzed:** 2026-05-05
**Purpose:** Companies use AI to filter candidates. I just gave candidates AI to choose companies.

---

## Languages & Runtimes
- Languages: node, shell, go
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
  - **node**: @google/generative-ai, dotenv, js-yaml, playwright

## Ports
- Inbound: none detected

## External Services *(source: source_scan)*
aistudio.google.com, api.hh.ru, api.lever.co, api.star-history.com, apply.workable.com, boards-api.greenhouse.io, boards.greenhouse.io, careers.cognigy.com, careers.mastercard.com, careers.salesforce.com, discord.gg, docs.renovatebot.com, example.com, github.com, greenhouse.io, hh.ru, janesmith.dev, job-boards.eu.greenhouse.io, job-boards.greenhouse.io, jobs.ashbyhq.com, jobs.example.com, jobs.lever.co, langfuse.com, linkedin.com, liveperson.com, mastercard.wd1.myworkdayjobs.com, openai.com, private.url, raw.githubusercontent.com, retool.com, sam-rivera.example.dev, santifer.io, trudvsem.ru, www.canva.com, www.dialpad.com, www.genesys.com, www.getmaxim.ai, www.getzep.com, www.gong.io, www.make.com, www.talkdesk.com, www.twilio.com

## Environment Variables
GEMINI_API_KEY

## Container Requirements
  standard (no special requirements)

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


## Credentials Required
  - API keys: GEMINI_API_KEY
  - Tokens: GITHUB_TOKEN

## MCP Servers
none detected

## Claude Plugins
career-ops

## Browser / Test Tools
playwright

## GitHub API Usage
No

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: acquire_lock, acquire_state_lock, attempt, auto-managed, avg, awk, basename, bash, batch-input, batch-prompt, batch-state, bc, career-ops, cat, check_prerequisites, claude, completed, completed_at, cut, date, dirname, error_msg, esc_date, esc_id, esc_jd_file, esc_report_num, esc_url, exit_code, failed, found, get_retries, get_status, grep, head, id, init_state, jd_file, lock_pid, logs, max_num, merge_tracker, mkdir, mv, next_report_num_unlocked, node, num, old_pid, pending, pending_count, pending_ids, pending_notes, pending_sources, pending_urls, pid_ids, pids, print, print_summary, process_offer, prompt, release_lock, release_state_lock, report, report_num, reserve_report_num, reserve_report_num_unlocked, retries, rm, rmdir, run_with_state_lock, running, score, score_count, score_match, score_sum, sed, see, sleep, started_at, tail, total, total_input, tr, tracker-additions, update_state, update_state_unlocked, url, usage, waited
  - **CI toolchain (GitHub Actions)**: checkout, codeql, dependency-review, first-interaction, go, labeler, node, release-please, sbom, stale

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `awk` → `awk`
  - `basename` → `coreutils`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `cat` → `coreutils`
  - `cut` → `coreutils`
  - `date` → `coreutils`
  - `dirname` → `coreutils`
  - `grep` → `grep` (needs: dpkg)
  - `head` → `coreutils`
  - `id` → `coreutils`
  - `mkdir` → `coreutils`
  - `mv` → `coreutils`
  - `rm` → `coreutils`
  - `rmdir` → `coreutils`
  - `sed` → `sed`
  - `sleep` → `coreutils`
  - `tail` → `coreutils`
  - `tr` → `coreutils`
