---
name: builder-project-context
description: builder-project dual role as control plane and reference project repo, 4-layer container architecture, how layers are managed and pushed
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
# builder-project Context

## Two Roles

`builder-project` (sun2admin/builder-project) serves two distinct roles:

1. **Control plane** — manages the entire 4-layer container stack. Contains source subdirectories for all 4 layers. Claude (running inside builder-project) makes changes to layer subdirs and pushes them to each layer's standalone GitHub repo, which triggers image builds via that repo's own CI/CD.

2. **Reference project repo** — an example AI project (Claude project files only: CLAUDE.md, .claude/, .mcp.json, memory). Loaded into the running container by a Layer 4 devcontainer repo at startup. Has no architectural role in the container stack.

## 4-Layer Container Stack

| Layer | Subdir in builder-project | Standalone repo | Published image |
|---|---|---|---|
| Layer 1 | `layer1-ai-depends/` | `sun2admin/layer1-ai-depends` | `ghcr.io/sun2admin/layer1-ai-depends` |
| Layer 2 | `layer2-ai-install/` | `sun2admin/layer2-ai-install` | `ghcr.io/sun2admin/layer2-ai-install:claude\|gemini` |
| Layer 3 | `layer3-ai-plugins/` (docs only) | 8 standalone plugin repos | `ghcr.io/sun2admin/claude-plugins-*` |
| Layer 4 | `layer4-devcontainer/` | e.g. `sun2admin/build-containers-with-claude` | (devcontainer config, no image) |

**Dependency cascade**: Layer 1 → Layer 2 → Layer 3 → Layer 4 inherits automatically on rebuild.

## How builder-project Manages Layers

Claude makes changes to a layer subdir in builder-project, then pushes those files to the standalone repo. The standalone repo's own GitHub Actions CI/CD builds and pushes the GHCR image. There is no root-level automation in builder-project — this is a manual, Claude-driven workflow.

**Layer 3 exception**: The 8 plugin repos are currently edited directly (not sourced from `layer3-ai-plugins/`). Consolidation into builder-project is planned.

## Project Repos (separate concept, not part of the stack)

Project repos contain only Claude/AI project files (CLAUDE.md, .claude/, memory, skills, .mcp.json). They are loaded into the container at start by `load-projects.sh` in the Layer 4 devcontainer.

- `builder-project` — reference example project repo
- `build-containers-with-claude` — reference example Layer 4 devcontainer repo

## Key Repos

- `sun2admin/builder-project` — the single control-plane repo; also the reference project repo
- `/workspace/claude/builder-project/` — live clone inside the running container

## Persistence Lifecycle

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start
~/.claude/projects/<canonical-path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
    ↑  /sync-prj-repos-memory skill
git repo (.claude/memory/*.md)  (committed, portable)
```

Named volume: `claude-code-config-${devcontainerId}` — persists across restarts, fresh on rebuild.

## Key Skills

- `/sync-prj-repos-memory` — syncs named volume memory → git repo, commits, pushes
- `load-projects.sh` — clones project repos, seeds memory on container start

## Canonical Path

`/workspace/claude/builder-project` → `-workspace-claude-builder-project`
Memory: `~/.claude/projects/-workspace-claude-builder-project/memory/`

## Ongoing Work

- Auto-restore init script for `.claude.json` backup — proposed, not yet implemented
- Layer 3 consolidation — plugin repo sources to be brought into `layer3-ai-plugins/`
- MCP binary + init scripts move from layer4-devcontainer to project repos — design in progress
