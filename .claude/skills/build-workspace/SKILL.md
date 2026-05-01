---
name: build-workspace
description: Scaffold a new Claude or Gemini workspace with all dependencies configured. Use this skill when the user wants to create, clone, or modify a workspace build — selecting a base image, AI CLI, plugin layer, and project repo. Invoke for any request involving building or setting up a development workspace.
shortcut: bw
usage: |
  /build-workspace [--dry-run]

  Lists saved builds in builds/, lets user pick existing (clone/modify) or create new.
  Walks through each layer, saves workspace.env, launches Claude.

  Options:
    --dry-run    Test the menu flow without executing commands or making changes
---

# /build-workspace

Master orchestrator for building a new Claude or Gemini development workspace.

## Entry Flow (Option A — list first)

1. Lists saved builds from `builds/` in the repo
2. User selects an existing build to **clone** or **modify**, or starts **new**
3. Walks through the layer wizard, pre-populated from the selected build
4. Saves final config to `builds/<name>/workspace.env`
5. Launches Claude in the workspace directory

## Layer Skills

Each layer is handled by a dedicated skill script:

| Layer | Script | Selects |
|---|---|---|
| Layer 1 | `build-layer1/build-layer1.sh` | Base image variant |
| Layer 2 | `build-layer2/build-layer2.sh` | AI CLI (claude/gemini) |
| Layer 3 | `build-layer3/build-layer3.sh` | Plugin layer (discovered from GitHub) |
| Layer 4 | `build-layer4/build-layer4.sh` | Project repo (clone + workspace init) |

Back navigation (`b`) at any layer re-runs the previous layer.

## Saved Build Format

```
builds/<name>/workspace.env
```

```bash
BASE_IMAGE=latest
AI_INSTALL=claude
PLUGIN_LAYER=claude-plugins-3f889e47
PROJECT_SELECTED=sun2admin/builder-project
WORKSPACE_DIR=/workspace/claude/builder-project
CREATED=2026-04-30
LAST_MODIFIED=2026-04-30
```

## Shared Library

`lib.sh` is sourced by all layer scripts and provides:
- Color codes (RED GREEN BLUE YELLOW CYAN NC)
- `run_cmd()` — dry-run wrapper
- `read_input()` — TTY/piped input handling
- `input_selection()` — menu validation, sets `$SELECTION`, returns 0/1/2
