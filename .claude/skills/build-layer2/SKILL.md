---
name: build-layer2
description: Layer 2 AI CLI selection step for the build-workspace wizard. Called by the build-workspace master skill to select claude or gemini. Not invoked directly by users.
---

# build-layer2

Selects the Layer 2 AI CLI (claude or gemini) for a workspace build.

## Usage

Called by `build-workspace.sh` with the current value as `$1`:

```bash
result=$(bash build-layer2.sh "$AI_INSTALL" 2>/dev/tty)
```

## Output

- **stdout**: selected AI_INSTALL value (`claude` or `gemini`)
- **stderr**: interactive menu UI
- **exit 0**: selection made
- **exit 1**: user quit
- **exit 2**: user wants to go back
