---
name: build-layer3
description: Layer 3 plugin layer discovery and selection step for the build-workspace wizard. Queries GitHub for available claude-plugins-* repos and presents a selection menu. Called by the build-workspace master skill. Not invoked directly by users.
---

# build-layer3

Discovers and selects the Layer 3 plugin layer for a workspace build.

## Usage

Called by `build-workspace.sh` with AI type and current plugin layer as arguments:

```bash
result=$(bash build-layer3.sh "$AI_INSTALL" "$PLUGIN_LAYER" 2>/dev/tty)
```

## Behavior

- For `claude`: queries GitHub for repos matching `claude-plugins-*` with `anthropic-plugins` topic
- For `gemini`: placeholder (gemini plugins coming soon), allows proceed or back
- If no repos found: warns and offers continue-without-plugin or back

## Output

- **stdout**: selected PLUGIN_LAYER short name (e.g. `claude-plugins-3f889e47`) or `none`
- **stderr**: interactive menu UI
- **exit 0**: selection made
- **exit 1**: user quit
- **exit 2**: user wants to go back
