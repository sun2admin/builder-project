---
name: Claude Code Memory Portability and Project State Architecture
description: How Claude Code stores project state outside project directory (~/.claude/projects/<path>/), the critical drawbacks, why build-with-claude commits memory to git, and best practices for portable/persistent memory across machines and container rebuilds.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## How Claude Code Creates/Uses ~/.claude/projects/<cwd-path>/

When Claude starts with cwd=/workspace/claude (a git repository):

1. **Derives project identifier from git repository root**
 - Path is canonicalized: strip leading `/`, replace `/` with `-`
 - `/workspace/claude/builder-project` → `workspace-claude-builder-project`
 - This becomes the subdirectory name
 - **Note**: No leading dash. All subdirectories within the same git repo share one memory directory.

2. **Creates project state directory**
 - `~/.claude/projects/workspace-claude/` is created
 - This directory is NOT in the project repo
 - This directory is NOT under /workspace/

3. **Project state directory contains:**
 - `memory/` — auto-memory files written by Claude during sessions
 - `<session-1>.jsonl`, `<session-2>.jsonl` — conversation transcripts
 - Session metadata and state

4. **When project exists outside ~/.claude**
 - Project source code: `/workspace/claude/` (on disk, in git)
 - Project state: `~/.claude/projects/workspace-claude/` (separate location)
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
 /workspace/claude/ (source code)
 ~/.claude/projects/workspace-claude/memory/ (memory)

Delete /workspace/claude/ → memory still exists but orphaned

Switch to Machine B:
 /workspace/claude/ (cloned from git)
 ~/.claude/projects/workspace-claude/memory/ (EMPTY on new machine)
 
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

2. **Seeding on startup (via load-projects.sh)**
 ```bash
 # Seed only memory/*.md with cp -n (no-overwrite preserves in-session writes on restart)
 mkdir -p ~/.claude/projects/workspace-claude/memory
 cp -n /workspace/claude/.claude/memory/*.md \
   ~/.claude/projects/workspace-claude/memory/
 ```

3. **Syncing back on completion (via /sync-prj-repos-memory skill)**
 ```bash
 # Copy memory back to repo
 cp ~/.claude/projects/workspace-claude/memory/*.md \
   /workspace/claude/.claude/memory/
 # Commit everything (skills/commands/etc already in repo from Claude's writes)
 git add -A && git commit && git push
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
$ cd /tmp && claude # Start Claude elsewhere

Result:
- ~/.claude/projects/workspace-claude/memory/ still exists
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
- ~/.claude/projects/workspace-claude/memory/ is fresh (empty)
- load-projects.sh runs: cp -n /workspace/claude/.claude/memory/*.md
    ~/.claude/projects/workspace-claude/memory/
- Memory is restored from git
- Claude has full context
```

## Best Practices (Confirmed Against Official Anthropic Docs)

### Official Statement on Portability
> *"Auto memory is machine-local. All worktrees and subdirectories within the same git repository share one auto memory directory. Files are not shared across machines or cloud environments."*

### For Single-Machine Projects
1. **Rely on auto-memory only** — `~/.claude/projects/` is fine
2. Use `CLAUDE.md` for permanent instructions
3. Skills, commands, agents, rules: commit to git (already portable)

### For Multi-Machine / Container / Team Projects

**The correct pattern (confirmed):**

1. **Commit memory to git**
 ```
 <project>/.claude/memory/*.md  (committed to git)
 ```

2. **Seed on container start (memory only)**
 ```bash
 mkdir -p ~/.claude/projects/<canonical-id>/memory
 cp -n <project>/.claude/memory/*.md ~/.claude/projects/<canonical-id>/memory/
 # Use cp -n to preserve in-session writes on restart
 ```

3. **Sync back at session end (memory + commit repo changes)**
 ```bash
 # Bring memory into repo
 cp ~/.claude/projects/<canonical-id>/memory/*.md <project>/.claude/memory/
 # Commit everything (skills/commands/etc already in repo from Claude's writes)
 git -C <project> add -A && git commit && git push
 ```

4. **Do NOT bulk-copy `.claude/` config into `~/.claude/projects/`**
 Claude reads skills, commands, agents, rules, settings.json directly from the repo.
 Seeding them into `~/.claude/projects/.claude/` is unnecessary and risks stale data.

### autoMemoryDirectory Option
```json
{
  "autoMemoryDirectory": "<project>/.claude/memory"
}
```
⚠️ Cannot be set in `.claude/settings.json` (project scope) — security restriction.
Set in `~/.claude/settings.json` (user scope) or `settings.local.json`.
If set, Claude writes memory directly to the repo path — no seeding needed.

### For Shared Teams
1. Commit `.claude/memory/` with session-learned patterns
2. Use `.claude/settings.json` for team-shared permissions
3. `.claude/settings.local.json` is auto-gitignored — machine-local overrides only
4. Skills, commands, agents, rules: committed to git, portable by default

### For CI/CD / Automation
1. Commit memory to git (required for reproducibility)
2. Seed with `cp -n` on container start (memory only)
3. Don't rely on `~/.claude/projects/` for config — Claude reads from repo directly

## Relationship Between Two Memory Systems

```
.claude/memory/ (Git-committed, portable, team-shared)
 ↓ load-projects.sh (seeds)
~/.claude/projects/<path>/memory/ (Named volume, transient, session-specific)
 ↓ Claude writes auto-memory
 ↑ /sync-prj-repos-memory skill (copies back to git)
.claude/memory/ (Committed again)
```

## Why This Matters for /build-project Skill

Every project scaffold must include:

1. **Directory structure**
 ```
 /workspace/<project>/.claude/memory/
 ```

2. **load-projects.sh in postStartCommand**
 ```bash
 # Seeds memory only — all other config read from repo directly
 mkdir -p ~/.claude/projects/<canonical-id>/memory
 cp -n /workspace/<project>/.claude/memory/*.md \
   ~/.claude/projects/<canonical-id>/memory/ 2>/dev/null || true
 ```

3. **A sync skill**
 - Copy memory back to git after sessions
 - Commit to preserve knowledge

4. **Initial .claude/memory/MEMORY.md**
 - Even if empty, provides seeding target
 - Gives structure for future memory

Without this: Memory is lost on rebuild or doesn't survive container lifecycle.
