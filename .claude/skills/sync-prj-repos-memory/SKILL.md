---
name: sync-prj-repos-memory
description: Sync session memory from named volume back to project git repos and commit all changes
shortcut: sync
usage: |
  /sync-prj-repos-memory [project-path]

  Syncs auto-memory from ~/.claude/projects/<path>/memory/ back to the
  project repo, stages all changes (memory + any skills/commands written
  during the session), commits, and pushes.

  Arguments:
    project-path   Optional. Absolute path to a specific project to sync.
                   If omitted and cwd is inside a git repo, syncs that project.
                   If omitted and cwd is outside any git repo, syncs ALL
                   projects found under /workspace/claude/.
---

# /sync-prj-repos-memory

Outbound half of the memory persistence lifecycle. Run this before rebuilding
the container to ensure all session memory and config changes are committed to git.

## Why This Exists

Claude writes auto-memory to `~/.claude/projects/<path>/memory/` (named volume),
not to the project repo. The named volume survives container restarts but is lost
on rebuild. This skill copies memory back to the repo and commits it so it
survives rebuilds and is portable across machines.

Skills, commands, agents, rules, and settings.json are written directly to the
project repo during sessions — this skill picks those up via `git add -A` too.

## Invocation Modes

| Invocation | Behavior |
|---|---|
| `/sync-prj-repos-memory` (inside git repo) | Sync current project only |
| `/sync-prj-repos-memory /workspace/claude/my-prj` | Sync specified project only |
| `/sync-prj-repos-memory` (outside any git repo) | Sync ALL projects in /workspace/claude/ |

## What Gets Committed

- `memory/*.md` — synced from named volume
- `skills/`, `commands/`, `agents/`, `rules/` — if modified during session
- `settings.json`, `CLAUDE.md`, `.mcp.json` — if modified during session
- `settings.local.json` — never committed (auto-gitignored, machine-local)

## Lifecycle

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start
~/.claude/projects/<path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
~/.claude/projects/<path>/memory/  (updated)
    ↑  /sync-prj-repos-memory  ← this skill
git repo (.claude/memory/*.md)  (committed, portable)
```
