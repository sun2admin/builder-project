# Dependency Analysis: builder-project

**Repo:** sun2admin/builder-project
**Analyzed:** 2026-05-07
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
- Inbound: 8888

## External Services *(source: init-firewall.sh)*
api.anthropic.com, claude.ai, marketplace.visualstudio.com, registry.npmjs.org, sentry.io, statsig.com, update.code.visualstudio.com, vscode.blob.core.windows.net

## Environment Variables
CLAUDE_CONFIG_DIR, COLORTERM, DEVCONTAINER, NODE_OPTIONS, PATH, PLAYWRIGHT_BROWSERS_PATH, PLAYWRIGHT_CHROMIUM_SANDBOX, SSH_AUTH_SOCK, TERM, TZ

## Container Requirements
  - Docker caps: NET_ADMIN, NET_RAW
  - User: claude
  - postStartCommand: `sudo /usr/local/bin/init-firewall.sh && /workspace/.devcontainer/scripts/init-ssh.sh && /workspace/.devcontainer/scripts/init-gh-token.sh && /workspace/.devcontainer/scripts/init-github-mcp.sh && /workspace/.devcontainer/scripts/load-projects.sh -live sun2admin/builder-project`
  - Volume: `claude-code-bashhistory-${devcontainerId}` → `/commandhistory`
  - Volume: `claude-code-config-${devcontainerId}` → `/home/claude/.claude`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/SharedFiles` → `/home/claude/data`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_claude_ed25519` → `/run/credentials/gh_claude_ed25519`
  - Volume: `${localEnv:HOME}/Downloads/ClaudeFiles/Config/gh_pat` → `/run/credentials/gh_pat`
  - ENV: `NODE_OPTIONS`
  - ENV: `CLAUDE_CONFIG_DIR`
  - ENV: `SSH_AUTH_SOCK`
  - ENV: `TERM`
  - ENV: `COLORTERM`

## Init Script Chain *(decomposed `postStartCommand` / `postCreateCommand`)*
  - **post_start_chain**:
      - ○ baked/external (sudo): `/usr/local/bin/init-firewall.sh`
      - ○ baked/external: `/workspace/.devcontainer/scripts/init-ssh.sh`
      - ○ baked/external: `/workspace/.devcontainer/scripts/init-gh-token.sh`
      - ○ baked/external: `/workspace/.devcontainer/scripts/init-github-mcp.sh`
      - ○ baked/external: `/workspace/.devcontainer/scripts/load-projects.sh` `-live sun2admin/builder-project`
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
  - **Tools/binaries (not in Dockerfile)**: aarch64, acceptable, add_marketplace, add_recommended, added, age, aggregate, ai_clis, all_plugins, all_plugins_with_marketplace, all_total, analyze_with_menu, analyzed_repos, anthropics, any, ascii_downcase, auth_user, author, available, available_json, awk, base, base64, base_count, base_dist_official, base_plugins, base_prebuilt, base_total, basename, bash, bc, branch, branches, build-args, build_category, build_project, cache, cache_file, cache_or_analyze, calculated_estimate, canonical, canonical_id, canonicalize_path, cat, cat_counts, cat_dir, cat_json, cat_label, category, cats, cats_tsv, caveman, cc, chmod, choice, choice-1, chown, claude, cli, clis_json, clone_repo, code_results, coding_additions, coding_total, collision_check, collision_menu, collision_recurse, commit_project, community_count, conflict, conflict_found, contains, contents, context, count, count_changed, cp, cr, create_plugin_set_hash, ctx, curl, cut, dash_results, date, deleted, description, detect_ai_signals, devcontainer, dig, dim, dirname, dist_sum, distribution, document-skills, documented, documented_base_size, duplicates, elapsed_ms, emit_build_json, empty_results, empty_selections, end_time, ensure_file, entries, env, err, estimated_size, except, exclude_flag, exists_in_lists, exit_code, expected, expected_all, expected_coding, expected_count, ext_total, fetch_marketplace_name, final_rel, find, found, generate_hash, get_authenticated_user, get_repo_owner, gh_ranges, gh_repo_check, git, github, grep, group_by, has, has_all_marketplaces, has_cache_dir, has_code_in_name, has_community, has_descriptions, has_distribution, has_financial, has_hash, has_image_tag, has_knowledge, has_name, has_official, has_plugins, has_seed_dir, has_skills, hash1, hash2, hash_coding, head, homepage, hookify, human, idx_to_cli, ies, include, indent_present, info, input, input_selection, ip, ips, ipset, iptables, iptables-save, is_array, is_plugins_array, is_valid, join, jq, jq_filter, json, json_array, keeps, key, keys, l1, l3, label, large_selection_count, latest, length, list_marketplaces, live_count, live_memory, live_name, live_path, live_repo, lower, lowercase, main_menu, map, mark, marketplace, marketplace_adds, marketplace_data, marketplace_distribution, marketplace_name, matrix, matrix_count, may, merged, mixedcase, mkdir, mkt, mkt_name, mktemp, modified, modified_count, mtime, mtime_days, mv, n-1, name, new-plugin-layer, new_entry, new_name, new_order, non-fatal, non_official_count, now, official_cache, official_count, or, order, original_count, other_repos, out, out_file, owner, owner_repo, packages, parse_args, password, pct, permissions, phase2_invoke, picked, playground, plugin, plugin_cats, plugin_count, plugin_descs, plugin_installs, plugin_lists, plugin_names, plugin_names_all, plugin_selections, plugin_selector_run, plugin_set1, plugin_set2, plugins, plugins_count, pre-installed, prebuilt_names, prebuilts, preflight, primary, print, print_summary, project_repo, project_repo_arg, python, python3, quit, raw, rc, read_input, rec_tag, reduce, redundancy, registry, remote_url, remove_marketplace, remove_recommended, repo, repo_name, repo_owner, reponame, reset, rest, result, result_count, results, rm, rsync, run_analyze, run_cmd, run_sync, run_test_suite, runs-on, sanitize_name, sanitized, schema_version, script, search_marketplace, search_results, secrets, sed, seed_memory, sel, sel_count, selected, selection_count, selections_json, selector, sha256sum, single, single_results, skill, skills_count, skills_field_count, sort, sort_by, ssh-agent, ssh-keyscan, stage_dir, standards_names, start_time, stat, stderr, stdout, step1_project_repo, step2_analyze_project, step3_category, step5_project_name, step6_ai_clis, step7_recommended_prompt, step8_plugin_selector, steps, still, strategy, sub-components, sync_memory, sync_project, sys, tags, target, target_memory, task, test_search_functionality, tmp, tmp_out, tokens, tostring, total, total_plugins, total_results, touch, tr, transcript, try, uname, uncategorized, uniq, unknown, uppercase, use_rec, use_recommended_l3, username, uses, valid_types, validate_repo, validation, value, via, view_recommended, warn, wc, workflow_dispatch, x86_64, xargs
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
  - `python3` → `python3` (needs: python3.11, libpython3-stdlib)
  - `rm` → `coreutils`
  - `script` → `bsdutils`
  - `sed` → `sed`
  - `sha256sum` → `coreutils`
  - `skill` → `procps`
  - `sort` → `coreutils`
  - `ssh-agent` → `openssh-client`
  - `ssh-keyscan` → `openssh-client`
  - `stat` → `coreutils`
  - `tar` → `tar`
  - `touch` → `coreutils`
  - `tr` → `coreutils`
  - `uname` → `coreutils`
  - `uniq` → `coreutils`
  - `wc` → `coreutils`
  - `x86_64` → `util-linux`
  - `xargs` → `findutils`
