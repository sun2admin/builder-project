---
name: build-layer4
description: Layer 4 project search, selection, GHCR validation, clone, and workspace initialization step for the build-workspace wizard. Searches GitHub for tagged project repos, validates GHCR images, and clones the selected project. Called by the build-workspace master skill. Not invoked directly by users.
---

# build-layer4

Handles project discovery, GHCR validation, cloning, and workspace initialization for Layer 4.

## Usage

Called by `build-workspace.sh` with AI type and current project as arguments:

```bash
result=$(bash build-layer4.sh "$AI_INSTALL" "$PROJECT_SELECTED" 2>/dev/tty)
```

## Behavior

1. Searches GitHub for repos tagged `<ai_install>-prj` (e.g. `claude-prj`)
2. Presents project list; user selects or skips
3. Validates GHCR image via `docker manifest inspect`
4. Clones project to `/workspace/<ai>/<name>/`
5. Runs `init-workspace.sh` if present, or seeds basic memory directory
6. Creates `sync-workspace-repo` skill in cloned project

## Output

- **stdout**: WORKSPACE_DIR path (e.g. `/workspace/claude/my-project`) or `/workspace/<ai>` if no project selected
- **stderr**: interactive menu UI and progress messages
- **exit 0**: done
- **exit 1**: user quit
- **exit 2**: user wants to go back
