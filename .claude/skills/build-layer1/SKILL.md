---
name: build-layer1
description: Layer 1 base image selection step for the build-workspace wizard. Called by the build-workspace master skill to select the base system image variant (light, latest, or playwright variants). Not invoked directly by users.
---

# build-layer1

Selects the Layer 1 base image variant for a workspace build.

## Usage

Called by `build-workspace.sh` with the current value as `$1`:

```bash
result=$(bash build-layer1.sh "$BASE_IMAGE" 2>/dev/tty)
```

## Output

- **stdout**: selected BASE_IMAGE value (e.g. `latest`)
- **stderr**: interactive menu UI
- **exit 0**: selection made
- **exit 1**: user quit
- **exit 2**: user wants to go back
