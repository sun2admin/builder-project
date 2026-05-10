# Dependency Analysis: build-stack-with-claude

**Repo:** sun2admin/build-stack-with-claude
**Analyzed:** 2026-05-10
**Purpose:** Layer 4 devcontainer test stack. Mirror of sun2admin/builder-project → layer4-devcontainer/ template. Created 2026-05-07 to validate the TTY / geometry fix without touching the production build-containers-with-claude

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
- Inbound: 8888

## External Services *(source: source_scan)*
none detected

## Environment Variables
CLAUDE_CONFIG_DIR, COLORTERM, NODE_OPTIONS, SSH_AUTH_SOCK, TERM

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
      - ✓ in-repo: `.devcontainer/scripts/init-ssh.sh`
      - ✓ in-repo: `.devcontainer/scripts/init-gh-token.sh`
      - ✓ in-repo: `.devcontainer/scripts/init-github-mcp.sh`
      - ✓ in-repo: `.devcontainer/scripts/load-projects.sh` `-live sun2admin/builder-project`
  - post_create_chain: none
  - **init_scripts (in-repo)**: .devcontainer/scripts/init-gh-token.sh, .devcontainer/scripts/init-github-mcp.sh, .devcontainer/scripts/init-ssh.sh, .devcontainer/scripts/load-projects.sh


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
  - **Tools/binaries (not in Dockerfile)**: aarch64, basename, canonical_id, canonicalize_path, cat, chmod, claude, clone_repo, cp, cut, dirname, git, live_count, live_name, live_path, live_repo, mkdir, non-fatal, other_repos, parse_args, pre-installed, repo_name, rm, sed, seed_memory, ssh-agent, ssh-keyscan, target, target_memory, touch, uname, x86_64

## System Dependencies *(tools → apt packages, via tool-deps.json cache)*
  - `basename` → `coreutils`
  - `cat` → `coreutils`
  - `chmod` → `coreutils`
  - `cp` → `coreutils`
  - `cut` → `coreutils`
  - `dirname` → `coreutils`
  - `git` → `git` (needs: libc6, libcurl3-gnutls, libexpat1, libpcre2-8-0, zlib1g)
  - `mkdir` → `coreutils`
  - `rm` → `coreutils`
  - `sed` → `sed`
  - `ssh-agent` → `openssh-client`
  - `ssh-keyscan` → `openssh-client`
  - `touch` → `coreutils`
  - `uname` → `coreutils`
  - `x86_64` → `util-linux`
