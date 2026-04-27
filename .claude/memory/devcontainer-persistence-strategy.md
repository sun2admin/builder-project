---
name: Docker Container Persistence Strategy for Claude Code
description: Why named volumes + git-committed project config is the correct approach for Claude memory/config persistence across container restarts and rebuilds
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## The Core Problem

Containers are ephemeral by design. On rebuild, the filesystem is lost entirely. But Claude Code's memory, configs, and plugins must survive across:
1. Container restarts (same devcontainerId)
2. Container rebuilds (new devcontainerId with fresh container image)
3. Team collaboration (shared project configs)

## The Solution: Hybrid Approach (build-with-claude pattern)

### Layer 1: Named Docker Volume
`"source=claude-code-config-${devcontainerId},target=/home/claude/.claude,type=volume"`

- Persists across **container restarts** (same devcontainerId)
- Gets **fresh volume on rebuild** (new devcontainerId) — this is acceptable because Layer 2 re-seeds it
- Stores: user configs, OAuth tokens, installed plugins, in-session memory writes
- Mount location: `/home/claude/.claude`

### Layer 2: Git-Committed Project Config
`/workspace/claude/.claude/` (checked into repo)

- Contains: memory/, commands/, agents/, rules/, settings.json
- Team-shared, version-controlled, reproducible
- Seeded into named volume on `postStartCommand` via `init-memory.sh`

### Layer 3: Seed-on-Start with No-Overwrite
`init-memory.sh`: `cp -n "$MEMORY_SRC"/*.md "$MEMORY_DEST/"`

- **First start**: copies all project memory from repo → named volume (empty volume)
- **On restart**: preserves any memories Claude wrote in-session (no-overwrite flag `-n`)
- **Elegant approach**: no complex merge logic, just simple copy-if-not-exists

### Layer 4: Environment Variable Override
`"CLAUDE_CONFIG_DIR": "/home/claude/.claude"`

- Tells Claude Code exactly where to find its config directory
- Without this, Claude looks in default `~/.claude/`
- Ensures Claude uses the named volume location

## Why This is Better Than Alternatives

| Approach | Problem | Impact |
|----------|---------|--------|
| **No volume mounting** | Files lost on rebuild | Memory/config gone on rebuild ✗ |
| **No git commit** | Can't share project config | Not reproducible, session state pollutes repo ✗ |
| **Just /workspace mount** | Every session write goes to git | Repo becomes cluttered with ephemeral state ✗ |
| **Just /home/claude/.claude without volume** | Lost on any rebuild | Memory gone immediately ✗ |
| **Hybrid (build-with-claude)** | Solves all above | Persistent, shared, reproducible ✓ |

## Key Insight: Separation of Concerns

- **Project Repo** (`/workspace/claude/.claude/`) = shared, team-visible, stable config
- **Named Volume** (`/home/claude/.claude/`) = user/session-specific, ephemeral-but-restart-persistent
- **init-memory.sh** = bridge that seeds the named volume from repo on start

On rebuild:
1. Fresh container created
2. Fresh named volume created (empty)
3. init-memory.sh copies project config from repo into named volume
4. Claude starts and sees fresh config

On restart (same container):
1. Container restarts
2. Named volume preserved (still has session-written memories + project config)
3. init-memory.sh runs again but `-n` flag prevents overwriting session writes
4. Claude starts and sees preserved state

## Why `cp -n` (No-Overwrite) is Crucial

```bash
cp -n "$MEMORY_SRC"/*.md "$MEMORY_DEST/" 2>/dev/null || true
```

- **First start (empty named volume)**: copies all files from repo ✓
- **Restart (existing named volume with session memories)**: preserves session writes ✓
- **Handles missing files gracefully**: `2>/dev/null || true` prevents error spam

Without `-n`:
- Every restart would overwrite in-session memory updates with repo version ✗
- Would lose work done during the session ✗

## Recommendation for /build-project Skill

All new projects (Minimal, Standard, Full) should use this exact pattern:

1. **devcontainer.json**
 - Named volume: `claude-code-config-${devcontainerId}` → `/home/claude/.claude`
 - `CLAUDE_CONFIG_DIR` env var pointing to `/home/claude/.claude`
 - `postStartCommand` that runs init-memory.sh

2. **init-memory.sh**
 - Copy structure: `cp -n` from `/workspace/<project>/.claude/memory/` → `/home/claude/.claude/projects/-workspace/memory/`
 - Graceful error handling

3. **Project Config Directories**
 - `.claude/memory/` (even if empty initially)
 - `.claude/commands/`
 - `.claude/agents/`
 - `.claude/rules/`
 - `.claude/settings.json`

This is the foundation for all projects, regardless of type or addons.