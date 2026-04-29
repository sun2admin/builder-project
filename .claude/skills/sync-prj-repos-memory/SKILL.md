---
name: sync-prj-repos-memory
description: Sync session memory from named volume back to project git repo and commit all changes
shortcut: sync
usage: |
  /sync-prj-repos-memory [project-path]

  Syncs auto-memory from ~/.claude/projects/<path>/memory/ back to the
  live project repo, stages all changes (memory + any skills/commands written
  during the session), commits, and pushes.

  Arguments:
    project-path   Optional. Absolute path to a specific project to sync.
                   If omitted, reads ~/live-project to determine the live project.

  Only syncs repos owned by the authenticated GitHub user. Non-owned repos
  are skipped entirely with a logged reason.
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
| `/sync-prj-repos-memory` (no args) | Read `~/live-project`, sync that project |
| `/sync-prj-repos-memory /workspace/claude/my-prj` | Sync specified project path |

`~/live-project` is written by `load-projects.sh` at container start. cwd is
not used — it can drift during a session via Bash tool `cd` commands.

## Ownership Filtering

Only repos owned by the authenticated GitHub user (`gh api user --jq '.login'`) are synced.
If a repo's remote owner differs from the authenticated user, the entire sync
is skipped (no memory sync, no commit, no push) and the reason is logged.
Repos with no detectable remote are treated as owned and synced normally.

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
