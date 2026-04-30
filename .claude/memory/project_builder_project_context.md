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

All 4 layers are managed within the single `sun2admin/builder-project` GitHub repo.
Each layer has its own subdirectory containing Dockerfiles, GitHub Actions, and config.

| Layer | Published Image | Contents |
|---|---|---|
| Layer 1 | `ghcr.io/sun2admin/layer1-ai-depends:latest` | System packages, Python, graphics libs, Playwright |
| Layer 2 | `ghcr.io/sun2admin/layer2-ai-install:claude` | Claude Code CLI, claude user, env setup |
| Layer 3 | `ghcr.io/sun2admin/claude-plugins-*:latest` | Pre-baked Claude Code plugins |
| Layer 4 Part 1 | devcontainer config subdir | devcontainer.json, init scripts, load-projects.sh |
| Layer 4 Part 2 | separate standalone repos | Claude/AI project files only, cloned by load-projects.sh |

**Layer 4 Part 2 repos are NOT inside builder-project.** They are separate repos cloned at
container start by `load-projects.sh` into `/workspace/<ai-name>/<repo-name>`.
`builder-project` itself is the reference implementation of a Part 2 repo.

## Key Repos

- `sun2admin/builder-project` — **the single GitHub repo** containing all layer source files as subdirectories (Layers 1–3 and Layer 4 Part 1); also serves as the reference Part 2 Claude project
- `/workspace/claude/builder-project/` — live project clone (loaded by load-projects.sh into the running container)

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
- Phase 3 (future): migrate `sync-prj-repos-memory` skill to `claude-global-config` repo and bake into layer2-ai-install (Layer 2)
