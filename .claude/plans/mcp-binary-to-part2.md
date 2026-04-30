# Plan: Move GitHub MCP Binary Ownership to project repo (builder-project)

## Problem
Currently the GitHub MCP server binary is owned by layer4-devcontainer (layer4-devcontainer subdir of builder-project):
- `scripts/bin/github-mcp-server-linux-amd64` + `linux-arm64` committed to layer4-devcontainer
- `init-github-mcp.sh` copies binary to `~/.local/bin/` at container start
- `update-github-mcp.yml` keeps binary updated in layer4-devcontainer repo
- `.mcp.json` in builder-project (project repo) points to absolute path `/home/claude/.local/bin/github-mcp-server`

This couples project repo to layer4-devcontainer's binary deployment. builder-project cannot run independently.

## Solution
Move binary ownership to builder-project (project repo). Confirmed working: `.mcp.json` resolves `command` relative to Claude's working directory, so `./scripts/bin/github-mcp-server` works when Claude is started from the project root.

## Changes Required

### builder-project (project repo) — ADD
- [ ] `scripts/bin/github-mcp-server-linux-amd64` — committed binary
- [ ] `scripts/bin/github-mcp-server-linux-arm64` — committed binary
- [ ] `scripts/bin/VERSION` — tracks current version
- [ ] `.github/workflows/update-github-mcp.yml` — automated weekly update workflow
- [ ] Update `.mcp.json` `command` to use relative path `./scripts/bin/github-mcp-server`

### layer4-devcontainer subdir in builder-project — REMOVE
- [ ] `scripts/bin/` directory and contents
- [ ] `init-github-mcp.sh` init script
- [ ] `update-github-mcp.yml` workflow
- [ ] Reference to `init-github-mcp.sh` in `postStartCommand` (devcontainer.json)

## PATH Management for scripts/bin/

For `gh` CLI and other binaries in `scripts/bin/` to be callable by name in bash tool commands, `scripts/bin/` must be on PATH. Claude Code does NOT auto-add project directories to PATH.

**Solution confirmed via official docs research:**
- Use a `SessionStart` hook with `$CLAUDE_ENV_FILE` to dynamically extend PATH
- `$CLAUDE_PROJECT_DIR` gives the project root without hardcoding
- Hook appends `export PATH="$CLAUDE_PROJECT_DIR/scripts/bin:$PATH"` to `$CLAUDE_ENV_FILE`
- Claude Code sources `$CLAUDE_ENV_FILE` before bash tool calls — fully portable, no layer4-devcontainer dependency

**Already implemented:** `.claude/hooks/session-start.sh` + `SessionStart` hook in `settings.json` (added as foundation, unconditional, works even when `scripts/bin/` is empty)

## Open Questions (see conversation)
1. Does `init-github-mcp.sh` become entirely unnecessary, or does the binary still need to be copied anywhere?
2. Does the arch detection logic (amd64 vs arm64) move into `.mcp.json`, or does a small wrapper script handle it?
3. How is the initial binary bootstrapped into a brand new builder-project repo before the GitHub Action has run?
4. Does `gh` CLI (system package) move to project repo via pre-built binary in `scripts/bin/`, or stay as layer4-devcontainer apt install?
5. Should `scripts/bin/` be gitignored in builder-project (download at runtime) or committed (current layer4-devcontainer approach)?

## Status
- [x] Relative path in `.mcp.json` tested and confirmed working
- [ ] Pending clarification on open questions above
- [ ] Implementation not started
