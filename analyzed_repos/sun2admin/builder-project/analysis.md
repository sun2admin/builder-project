# Dependency Analysis: builder-project

**Repo:** sun2admin/builder-project
**Analyzed:** 2026-05-06
**Purpose:** Example Layer 4 Claude project demonstrating the multi-project workspace architecture.

---

## Languages & Runtimes
- Languages: python, shell
- Runtime extras: none detected
- Versions: none detected
- Base image: `node:22-slim`

## System Packages
gh, ipykernel, jupyterlab, numpy, pandas, pdfplumber, pymupdf, pypdf, python3-pip, reportlab, weasyprint

## Global JS Package Installs *(Dockerfile npm/pnpm/yarn/bun globals)*
@google/gemini-cli, @anthropic-ai/claude-code

## Dockerfile Python Installs *(`pip` / `pipx` in RUN blocks)*
jupyterlab, ipykernel, pdfplumber, pymupdf, pypdf, reportlab, weasyprint, pandas, numpy, playwright, playwright

## Dockerfile Go Installs *(`go install` in RUN blocks)*
none detected

## Libraries
  none detected

## Ports
- Inbound: none detected

## External Services *(source: init-firewall.sh)*
api.anthropic.com, claude.ai, marketplace.visualstudio.com, registry.npmjs.org, sentry.io, statsig.com, update.code.visualstudio.com, vscode.blob.core.windows.net

## Environment Variables
DEVCONTAINER, PATH, PLAYWRIGHT_BROWSERS_PATH, PLAYWRIGHT_CHROMIUM_SANDBOX, TZ

## Container Requirements
  standard (no special requirements)

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - post_start_chain: none
  - post_create_chain: none


## Credentials Required
  - Tokens: GITHUB_TOKEN
  - SSH key required

## MCP Servers
github

## Claude Plugins
none detected

## Browser / Test Tools
none detected

## GitHub API Usage
Yes

## Inferred from Source *(tools/commands found in repo files)*
  - **Tools/binaries (not in Dockerfile)**: aarch64, acceptable, added, aggregate, ai, all_plugins, all_plugins_with_marketplace, all_total, anthropics, args, ascii_downcase, auth_user, awk, back, base, base_count, base_dist_official, base_image, base_plugins, base_prebuilt, base_total, basename, bash, bc, branch, branches, build-args, cache_file, calculated_estimate, call_layer, canonical, canonical_id, canonicalize_path, cat, chmod, chown, claude, clone_repo, code_results, coding_additions, coding_total, commit_project, community_count, conflict, conflict_found, contains, contents, context, count, cp, create_plugin_set_hash, create_sync_skill, curl, current, cut, dash_results, date, deleted, description, devcontainer, dig, dir, dirname, dist_sum, distribution, document-skills, documented, documented_base_size, duplicates, elapsed_ms, emit_build_json, empty_results, empty_selections, end_time, env, estimated_size, exists_in_lists, exit_code, expected, expected_all, expected_coding, expected_count, ext_total, find, found, gemini, generate_hash, get_authenticated_user, get_repo_owner, gh_ranges, ghcr_image, git, github, grep, has, has_all_marketplaces, has_cache_dir, has_code_in_name, has_community, has_descriptions, has_distribution, has_financial, has_hash, has_image_tag, has_knowledge, has_name, has_official, has_plugins, has_seed_dir, has_skills, hash1, hash2, hash_coding, head, hookify, include, indent_present, index, input, input_selection, invoke_tool, ip, ips, ipset, iptables, iptables-save, is_array, is_plugins_array, is_valid, join, jq, json, keys, label, large_selection_count, latest, length, lift, live_count, live_name, live_path, live_repo, load_build, lower, lowercase, map, marketplace, marketplace_adds, marketplace_data, marketplace_distribution, marketplace_name, matrix, matrix_count, may, mixedcase, mkdir, mktemp, mocked, modified, modified_count, mv, name, new-plugin-layer, new_entry, non-fatal, non_official_count, now, num, offer, official_cache, official_count, original_count, other_repos, owner, packages, parse_args, password, permissions, phase1_ai_cli, phase1_entry, phase1_overrides, phase1_plugin_repos, phase1_project_repo, phase2_invoke, playground, plugin_count, plugin_installs, plugin_lists, plugin_names_all, plugin_set1, plugin_set2, plugins, plugins_count, pre-installed, prebuilt_names, prebuilts, print, prompt, prompt_build_name, python, rc, read_input, redundancy, registry, remote_url, repo, repo_name, repo_owner, reponame, result, result_count, results, rm, rsync, run_cmd, run_layer, run_test_suite, runs-on, save_build, script, search_marketplace, search_results, secrets, sed, seed_memory, selection_count, sha256sum, short, shortcut, single, single_results, skill, skills_count, skills_field_count, sort, space-separated, ssh-agent, ssh-keyscan, standards_names, start_time, stderr, stdout, steps, still, strategy, sub-components, sync_dir, sync_memory, sync_project, tags, target, target_memory, test_search_functionality, total, total_plugins, total_results, touch, tr, uname, uniq, uppercase, username, uses, valid_types, validate_and_clone, validation, value, wc, workflow_dispatch, workspace, x86_64, xargs
  - **Confirmed by Dockerfile**: gh
  - **CI toolchain (GitHub Actions)**: build-push, buildx, cat, checkout, chmod, curl, env, gh, git, grep, id, login, mv, qemu, sed, sha256sum, tar
  - **Python imports (not in manifest)**: build_stack, jsonschema, pytest

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `aggregate` → `aggregate` (needs: libc6)
  - `awk` → `awk`
  - `base` → `base`
  - `basename` → `coreutils`
  - `bash` → `bash` (needs: base-files, debianutils)
  - `cat` → `coreutils`
  - `chmod` → `coreutils`
  - `chown` → `coreutils`
  - `context` → `context`
  - `cp` → `coreutils`
  - `curl` → `curl` (needs: libc6, libcurl4, zlib1g)
  - `cut` → `coreutils`
  - `date` → `coreutils`
  - `dig` → `bind9-dnsutils`
  - `dir` → `coreutils`
  - `dirname` → `coreutils`
  - `env` → `coreutils`
  - `find` → `findutils`
  - `gh` → `gh` (needs: libc6)
  - `git` → `git` (needs: libc6, libcurl3-gnutls, libexpat1, libpcre2-8-0, zlib1g)
  - `grep` → `grep` (needs: dpkg)
  - `head` → `coreutils`
  - `id` → `coreutils`
  - `ip` → `iproute2`
  - `ipset` → `ipset` (needs: libc6, libipset13)
  - `iptables` → `iptables` (needs: libip4tc2, libip6tc2, libxtables12, netbase, libc6)
  - `join` → `coreutils`
  - `jq` → `jq` (needs: libjq1, libc6)
  - `login` → `login`
  - `mkdir` → `coreutils`
  - `mktemp` → `coreutils`
  - `mv` → `coreutils`
  - `python` → `python`
  - `rm` → `coreutils`
  - `script` → `bsdutils`
  - `sed` → `sed`
  - `sha256sum` → `coreutils`
  - `skill` → `procps`
  - `sort` → `coreutils`
  - `ssh-agent` → `openssh-client`
  - `ssh-keyscan` → `openssh-client`
  - `tar` → `tar`
  - `touch` → `coreutils`
  - `tr` → `coreutils`
  - `uname` → `coreutils`
  - `uniq` → `coreutils`
  - `wc` → `coreutils`
  - `x86_64` → `util-linux`
  - `xargs` → `findutils`
