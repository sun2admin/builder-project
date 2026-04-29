---
name: builder-project-context
description: builder-project purpose, 4-layer container architecture, key repos, ongoing work, and persistence lifecycle
type: project
originSessionId: 5c59a0d5-1064-4e64-9cef-f4c77d757503
---
# builder-project Context

## Purpose

`builder-project` (sun2admin/builder-project) is a Layer 4 devcontainer project used to build, manage, and modify other GitHub repos using Claude Code. It is the "live project" — the project Claude runs in — not a project being built.

## 4-Layer Container Architecture

| Layer | Image | Contents |
|---|---|---|
| Layer 1 | `ghcr.io/sun2admin/base-ai-layer:latest` | System packages, Python, graphics libs, Playwright |
| Layer 2 | `ghcr.io/sun2admin/ai-install-layer:claude` | Claude Code CLI, claude user, env setup |
| Layer 3 | `ghcr.io/sun2admin/claude-plugins-a7f3d2e8:latest` | Pre-baked Claude Code plugins |
| Layer 4 | `build-with-claude` (this repo) | devcontainer.json referencing Layer 3 |

Stage2 = `sun2admin/build-with-claude-stage2` — the active devcontainer config repo.
Stage3 = `sun2admin/build-with-claude-stage3` — clone of stage2, used for testing new configs.

## Key Repos

- `sun2admin/builder-project` — live project repo (skills, commands, plans, memory)
- `sun2admin/build-with-claude-stage2` — devcontainer config (load-projects.sh, devcontainer.json, init scripts)
- `sun2admin/build-with-claude-stage3` — stage2 clone for testing
- `/workspace/.devcontainer/` — bind-mounted from the host workspace (stage2 or stage3 repo)
- `/workspace/claude/builder-project/` — live project clone (bind mount via load-projects.sh)

## Persistence Lifecycle

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start  (live project only)
~/.claude/projects/<canonical-path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
~/.claude/projects/<canonical-path>/memory/  (updated in named volume)
    ↑  /sync-prj-repos-memory skill
git repo (.claude/memory/*.md)  (committed, portable)
```

Named volume: `claude-code-config-${devcontainerId}` — persists across rebuilds (same devcontainerId = same workspace path).

## Key Skills and Plans

- `/sync-prj-repos-memory` — syncs named volume memory → git repo, commits, pushes
  - Plan: `.claude/plans/sync-prj-repos-memory-skill.md`
- `load-projects.sh` — clones live repo, seeds memory, writes `~/live-project`
  - Plan: `.claude/plans/load-projects-retroactive.md`

## Canonical Path

Claude Code converts `/workspace/claude/builder-project` → `-workspace-claude-builder-project` (leading dash, all `/` become `-`). Memory lives at `~/.claude/projects/-workspace-claude-builder-project/memory/`.

## Ongoing Work

- Auto-restore init script for `.claude.json` backup — proposed, not yet implemented
- Phase 3 (future): migrate `sync-prj-repos-memory` skill to `claude-global-config` repo and bake into ai-install-layer (Layer 2)
