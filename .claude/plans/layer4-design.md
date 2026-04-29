# Plan: Layer 4 Architecture Design

## Overview

Layer 4 is split into two distinct parts. Part 2 dictates what Part 1 contains.

**Part 1 — Container/Dependency Layer**
Subdirectory within `sun2admin/builder-project` (single repo).
Contains: devcontainer.json, init scripts, firewall rules, Layer 3 image reference.

**Part 2 — Claude Project Repos**
Subdirectory within `sun2admin/builder-project` (single repo).
`builder-project` itself is the reference implementation of a Part 2 repo.
Contains: Claude files only (CLAUDE.md, .claude/, .mcp.json, skills, memory).
Self-contained and portable — usable independently of the 4-layer architecture.
Cloned to `/workspace/<ai-name>/<repo-name>`. Only one AI workspace exists at a time.

---

## gh CLI and MCP Binary (see also: mcp-binary-to-part2.md)

### Current State
- `gh` CLI installed via apt in Part 1 image (Layer 1/2)
- GitHub MCP server binary committed to Part 1 (`scripts/bin/`), deployed by `init-github-mcp.sh`
- `.mcp.json` in Part 2 points to absolute path `/home/claude/.local/bin/github-mcp-server`

### Confirmed: Both Can Move to Part 2
- `gh` CLI is distributed as pre-built binaries (not apt-only) — can be committed to `scripts/bin/`
- MCP server binary: relative paths in `.mcp.json` confirmed working (tested)
- PATH management solved: `SessionStart` hook + `$CLAUDE_ENV_FILE` + `$CLAUDE_PROJECT_DIR`
  dynamically adds `scripts/bin/` to PATH without hardcoding — fully portable

### Hook Already Implemented
`.claude/hooks/session-start.sh` adds `$CLAUDE_PROJECT_DIR/scripts/bin` to PATH at session start.
Wired in `settings.json` as a `SessionStart` hook. Committed to builder-project.

### Open Questions
1. Arch detection for binaries (amd64 vs arm64) — wrapper script or `.mcp.json` logic?
2. Bootstrap: how is `scripts/bin/` populated in a brand new Part 2 repo before CI runs?
3. Should binaries be committed to git (current Part 1 approach) or downloaded at container start?
4. `update-github-mcp.yml` moves to Part 2 — confirmed same file exists in all Part 1 repos

---

## Init Scripts (SSH, PAT, Firewall)

### Current State
All three run via `postStartCommand` in devcontainer.json (Part 1), before the project repo is cloned:

```
1. init-firewall.sh     ← sudo, iptables
2. init-ssh.sh          ← loads SSH key from /run/credentials/
3. init-gh-token.sh     ← reads PAT from /run/credentials/, writes ~/.profile
4. init-github-mcp.sh   ← copies MCP binary to ~/.local/bin/
5. load-projects.sh     ← clones project repo
```

### What Can Move to Part 2

**`init-ssh.sh`** — Movable. Which key to load is project-specific. Requires reordering.

**`init-gh-token.sh`** — Movable. Which PAT to use is project-specific. Requires reordering.

**`init-firewall.sh`** — Execution stays in Part 1 (requires sudo). But firewall *rules*
(which ports) could be declared in Part 2 and sourced by Part 1's script.

**Credential bind mounts** — Always Part 1. devcontainer.json controls what gets mounted
at `/run/credentials/`. Part 2 can declare what it expects but cannot mount them itself.

### The Chicken-and-Egg Problem
Project repo isn't cloned until step 5, but steps 2–4 need credentials that the project
would define. Can't run project scripts before the project exists on disk.

### Proposed Reordering
Part 1 maintains a **minimal bootstrap credential** (generic deploy key or scoped PAT)
just to clone the project repo. Then project scripts handle everything else:

```
1. init-firewall.sh (Part 1 — sources rules from project if available)
2. clone project repo (Part 1 — minimal bootstrap auth only)
3. $PROJECT/scripts/init-ssh.sh    (Part 2 — which key, which config)
4. $PROJECT/scripts/init-pat.sh    (Part 2 — which PAT, how to expose it)
5. $PROJECT/scripts/init-mcp.sh    (Part 2 — MCP binary, relative path)
```

### What Stays in Part 1 No Matter What
- Actual `iptables` commands (sudo requirement)
- Credential bind mounts (`/run/credentials/` entries in devcontainer.json)
- Bootstrap clone credential (minimum to clone the project repo)

### Open Questions
1. What is the bootstrap credential for cloning? Generic deploy key? Scoped PAT in Part 1?
2. Should firewall rules be declared in Part 2 as a config file sourced by Part 1?
3. Ordering change — does cloning the repo before SSH setup break anything currently?

---

## Status
- [ ] Design discussion only — no implementation started
- [ ] Pending resolution of open questions
- [ ] Depends on decisions in mcp-binary-to-part2.md
