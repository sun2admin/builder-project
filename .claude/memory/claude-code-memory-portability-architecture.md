---
name: Claude Code Memory Portability and Project State Architecture
description: How Claude Code stores project state outside project directory (~/.claude/projects/<path>/), the critical drawbacks, why build-with-claude commits memory to git, and best practices for portable/persistent memory across machines and container rebuilds.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## How Claude Code Creates/Uses ~/.claude/projects/<cwd-path>/

When Claude starts with cwd=/workspace/claude (a git repository):

1. **Derives project identifier from git repository**
   - Git repo URL or path is canonicalized
   - `/workspace/claude` → `-workspace-claude`
   - This becomes the subdirectory name

2. **Creates project state directory**
   - `~/.claude/projects/-workspace-claude/` is created
   - This directory is NOT in the project repo
   - This directory is NOT under /workspace/

3. **Project state directory contains:**
   - `memory/` — auto-memory files written by Claude during sessions
   - `<session-1>.jsonl`, `<session-2>.jsonl` — conversation transcripts
   - Session metadata and state

4. **When project exists outside ~/.claude**
   - Project source code: `/workspace/claude/` (on disk, in git)
   - Project state: `~/.claude/projects/-workspace-claude/` (separate location)
   - These are **two completely independent directory trees**

## Critical Drawback: Memory NOT Portable

### The Problem

Auto-memory is stored at: `~/.claude/projects/<project>/memory/`

This path is **outside the project directory** and **outside version control**.

**Consequences:**
1. **Not in Git** — memory doesn't travel with your code
2. **Machine-specific** — different machines have different `~/.claude/projects/`
3. **Lost on Delete** — deleting project directory leaves memory orphaned
4. **Container-specific** — container rebuild = fresh named volume = fresh memory (if not seeded)
5. **Not Portable** — can't easily move projects to another machine

### Example: What Happens

```
Machine A:
  /workspace/claude/                   (source code)
  ~/.claude/projects/-workspace-claude/memory/   (memory)

Delete /workspace/claude/ → memory still exists but orphaned

Switch to Machine B:
  /workspace/claude/                   (cloned from git)
  ~/.claude/projects/-workspace-claude/memory/   (EMPTY on new machine)
  
Claude has NO memory of previous work
```

### Why This Happens

Claude Code's design assumes:
- Users work on same machine
- Project path is constant
- ~/.claude is persistent

This breaks in:
- Multi-machine workflows (laptop + desktop)
- Container/cloud environments (ephemeral ~/.claude)
- CI/CD pipelines
- Team collaboration

## Why build-with-claude Commits Memory to Git

build-with-claude solves this by:

1. **Committing memory to git**
   ```
   /workspace/claude/.claude/memory/MEMORY.md
   /workspace/claude/.claude/memory/*.md
   ```

2. **Seeding on startup**
   ```bash
   # init-memory.sh
   cp -n /workspace/claude/.claude/memory/*.md \
         ~/.claude/projects/-workspace-claude/memory/
   ```

3. **Syncing back on completion**
   ```bash
   # /update-build-with-claude skill
   cp ~/.claude/projects/-workspace-claude/memory/*.md \
       /workspace/claude/.claude/memory/
   git add .claude/memory/
   git commit
   ```

This workaround:
- ✓ Makes memory portable (in git)
- ✓ Survives container rebuilds
- ✓ Shares memory across team
- ✓ Persists indefinitely
- ✗ Requires manual sync (not automatic)

## What Happens If Project Directory Is Deleted?

### Scenario 1: Project directory deleted, ~/.claude/projects/ intact

```
$ rm -rf /workspace/claude/
$ cd /tmp && claude      # Start Claude elsewhere

Result:
- ~/.claude/projects/-workspace-claude/memory/ still exists
- All session transcripts still there
- BUT: No way to access them (no cwd = /workspace/claude)
- Memory is orphaned but still on disk
```

Claude can still access everything IF you:
1. Clone the project again to /workspace/claude
2. `cd /workspace/claude && claude`
3. Claude recognizes the project and loads the orphaned memory

### Scenario 2: Project directory deleted, memory committed to git

```
$ rm -rf /workspace/claude/
$ git clone https://github.com/user/claude-project /workspace/claude
$ cd /workspace/claude && claude

Result:
- ~/.claude/projects/-workspace-claude/memory/ is fresh (empty)
- init-memory.sh runs: cp /workspace/claude/.claude/memory/* ~/.claude/...
- Memory is restored from git
- Claude has full context
```

## Best Practices

### For Single-Machine Projects
1. **Rely on auto-memory only**
   - Memory stored in ~/.claude/projects/ is fine
   - Use CLAUDE.md for permanent instructions
   - Use auto-memory for learned patterns

### For Multi-Machine / Container / Team Projects
1. **Commit memory to git** (what build-with-claude does)
   ```
   /workspace/claude/.claude/memory/     (committed to git)
   ```

2. **Set autoMemoryDirectory to project-local** (if supported)
   ```json
   {
     "autoMemoryDirectory": ".claude/memory"
   }
   ```
   ⚠️ NOTE: This cannot be set in .claude/settings.json (project scope) for security
   Set in: `~/.claude/settings.local.json` (user scope)

3. **Use init-memory.sh pattern**
   ```bash
   mkdir -p ~/.claude/projects/<project>/memory
   cp -n /workspace/<project>/.claude/memory/*.md ~/.claude/projects/<project>/memory/
   ```

4. **Use sync skill** (like /update-build-with-claude)
   ```bash
   cp ~/.claude/projects/<project>/memory/*.md /workspace/<project>/.claude/memory/
   git add .claude/memory/
   git commit "Update memory from session"
   ```

### For Shared Teams
1. Use .claude/CLAUDE.md for permanent team instructions
2. Commit .claude/memory/ with team-learned patterns
3. Use .claude/settings.json for team-shared permissions
4. Each developer has .claude/settings.local.json (gitignored)

### For CI/CD / Automation
1. Commit memory to git (required for reproducibility)
2. Use init-memory.sh to seed on container start
3. Don't rely on ~/.claude/projects/ (will be fresh)
4. Always assume memory is ephemeral unless seeded from git

## Relationship Between Two Memory Systems

```
.claude/memory/             (Git-committed, portable, team-shared)
   ↓ init-memory.sh (seeds)
~/.claude/projects/<path>/memory/  (Named volume, transient, session-specific)
   ↓ Claude writes auto-memory
   ↑ /sync-memory skill (copies back to git)
.claude/memory/             (Committed again)
```

## Why This Matters for /build-project Skill

Every project scaffold must include:

1. **Directory structure**
   ```
   /workspace/<project>/.claude/memory/
   ```

2. **init-memory.sh in postStartCommand**
   ```bash
   #!/bin/bash
   MEMORY_SRC="/workspace/<project>/.claude/memory"
   MEMORY_DEST="~/.claude/projects/<project-id>/memory"
   mkdir -p "$MEMORY_DEST"
   cp -n "$MEMORY_SRC"/*.md "$MEMORY_DEST/" 2>/dev/null || true
   ```

3. **A sync skill**
   - Copy memory back to git after sessions
   - Commit to preserve knowledge

4. **Initial .claude/memory/MEMORY.md**
   - Even if empty, provides seeding target
   - Gives structure for future memory

Without this: Memory is lost on rebuild or doesn't survive container lifecycle.
