# Dependency Analysis: builder-project

**Repo:** sun2admin/builder-project
**Analyzed:** 2026-05-05
**Purpose:** Example Layer 4 Claude project demonstrating the multi-project workspace architecture.

---

## Languages & Runtimes
- Languages: shell, node, python
- Runtime extras: bun
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
  - **Tools/binaries (not in Dockerfile)**: aarch64, acceptable, action, added, aggregate, ai, all_deps, all_doms, all_plugins, all_plugins_with_marketplace, all_scripts, all_tools, all_total, and, anthropics, api, apk, apt, args, ascii_downcase, auth, auth_user, awk, axios, back, badge_re, baked, base, base_count, base_dist_official, base_image, base_no_ver, base_plugins, base_prebuilt, base_total, basename, bash, bc, block, body, branch, branches, buf, build-, build-args, builder, bun, cache, cache_file, cache_updated, calculated_estimate, call_layer, cand, canonical, canonical_id, canonicalize_path, caps, capture_output, cargo, cat, chain, chmod, chown, ci_tools, claude, cleanup, clone_repo, cmd, cmds, code_fence, code_results, coding_additions, coding_total, comment_re, commit_project, community_count, conflict, conflict_found, contains, content, contents, context, count, cp, create_plugin_set_hash, create_sync_skill, curl, current, cut, dash_results, data, date, def, deleted, deno, dep_str, deps, description, devcontainer, dict, dig, dir, dirname, dist_sum, distribution, dm, document-skills, documented, documented_base_size, domain_re, domain_set, domains, domains_high, domains_medium, doms, dsa, duplicates, ecdsa, ed25519, elapsed_ms, emit_build_json, empty_results, empty_selections, end_time, env, errors, estimated_size, except, exists_in_lists, exit_code, expected, expected_all, expected_coding, expected_count, explicit_pkgs, ext_total, exts, find, firewall, fmt, fmt_container, fmt_creds, found, frozenset, fw, fw_any, gemini, generate_hash, get_authenticated_user, get_repo_owner, getattr, gh_any, gh_ranges, ghcr_image, git, github, go-github, grep, grpc, has, has_all_marketplaces, has_cache_dir, has_code_in_name, has_community, has_descriptions, has_distribution, has_financial, has_hash, has_image_tag, has_inferred, has_knowledge, has_name, has_official, has_plugins, has_seed_dir, has_skills, hash1, hash2, hash_coding, hdr, head, hookify, http, id_, id_rsa, img, import, in-repo, in_repo_scripts, include, indent_present, indented, index, inf, inferred_tools, init-firewall, init_scripts, input, input_selection, invoke_tool, ip, ips, ipset, iptables, iptables-save, is_array, is_plugins_array, is_valid, items, join, joined, jq, json, key, keys, known_hosts, kw, label, lang, large_selection_count, latest, len, length, libs, lift, line, lines, live_count, live_name, live_path, live_repo, load_build, lower, lowercase, map, marker, marketplace, marketplace_adds, marketplace_data, marketplace_distribution, marketplace_name, matrix, matrix_count, may, md, merged, mixedcase, mkdir, mktemp, mocked, modified, modified_count, more, mounts, mv, name, needs, new-plugin-layer, new_entry, next, nft, node, node_builtins, node_builtins_raw, node_libs, non-fatal, non_official_count, now, num, offer, official_cache, official_count, only, open, or, original_count, os, other_repos, owner, packages, paras, parse_args, parse_content, parsed, parts, password, pat, patch, path, pattern, pc_chain, perl, permissions, phase1_ai_cli, phase1_entry, phase1_overrides, phase1_plugin_repos, phase1_project_repo, phase2_invoke, pip3, pipx, pkg, pkgs, playground, pline, plugin_count, plugin_installs, plugin_lists, plugin_names_all, plugin_set1, plugin_set2, plugins, plugins_count, pnpm, ports, post, pre-installed, prebuilt_names, prebuilts, preview, print, prompt, prompt_build_name, prose, ps_chain, ps_doms, ps_fw, ps_gh, ps_scripts, ps_ssh, put, py_imports, py_imports_found, python3, python_libs, r2, raw, rc, re, read_input, redundancy, registry, rel, remote_url, repo, repo_name, repo_owner, reponame, request, requests, require, rest, result, result_count, results, rm, rsa, rsync, ruby, run_cmd, run_content, run_layer, run_test_suite, runner, runs-on, rust_ver, rv, save_build, script, search_marketplace, search_results, secrets, sed, seed_memory, selection_count, servers, setup, sh, sha256sum, shallow, shell_files, short, shortcut, single, single_results, skill, skill_dir, skills_count, skills_field_count, sort, space-separated, ssh, ssh-add, ssh-agent, ssh-keygen, ssh-keyscan, ssh_any, standard_lib, standards_names, start_time, stderr, stdlib_path, stdlib_py, stdout, step, steps, still, str, strategy, stripped, sub-components, sudo, sync_dir, sync_memory, sync_project, sys, sys_deps, system_deps, tags, tail, target, target_memory, task_files, test_search_functionality, text, token, toks, tool, tool_deps_cache, tool_deps_path, toolchain, tools, tools_found, total, total_plugins, total_results, touch, tr, try, ts_imports, ts_imports_found, txt, ufw, uname, uniq, uppercase, url, urllib, username, uses, valid_types, validate_and_clone, validation, value, vk, wc, wf, wget, which, workflow_dispatch, workspace, wrapper, x86_64, xargs
  - **Confirmed by Dockerfile**: gh
  - **CI toolchain (GitHub Actions)**: build-push, buildx, cat, checkout, chmod, curl, env, gh, git, grep, id, login, mv, qemu, sed, sha256sum, tar
  - **Python imports (not in manifest)**: build_stack, jsonschema

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `aggregate` → `aggregate` (needs: libc6)
  - `apt` → `apt` (needs: adduser, gpgv, libapt-pkg6.0, debian-archive-keyring, libc6)
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
  - `fmt` → `coreutils`
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
  - `more` → `util-linux`
  - `mv` → `coreutils`
  - `patch` → `patch`
  - `perl` → `perl` (needs: perl-base, perl-modules-5.36, libperl5.36)
  - `pip3` → `python3-pip`
  - `python3` → `python3` (needs: python3.11, libpython3-stdlib)
  - `rm` → `coreutils`
  - `ruby` → `ruby`
  - `script` → `bsdutils`
  - `sed` → `sed`
  - `sh` → `diversion by dash from`
  - `sha256sum` → `coreutils`
  - `skill` → `procps`
  - `sort` → `coreutils`
  - `ssh` → `ssh`
  - `ssh-add` → `openssh-client`
  - `ssh-agent` → `openssh-client`
  - `ssh-keygen` → `openssh-client`
  - `ssh-keyscan` → `openssh-client`
  - `sudo` → `sudo` (needs: libaudit1, libc6, libpam0g, libselinux1, zlib1g)
  - `tail` → `coreutils`
  - `tar` → `tar`
  - `touch` → `coreutils`
  - `tr` → `coreutils`
  - `uname` → `coreutils`
  - `uniq` → `coreutils`
  - `wc` → `coreutils`
  - `wget` → `wget` (needs: libc6, libgnutls30, libidn2-0, libnettle8, libpcre2-8-0)
  - `x86_64` → `util-linux`
  - `xargs` → `findutils`
