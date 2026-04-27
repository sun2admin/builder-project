# new-plugin-layer

Create a new Claude Code plugin layer image on top of `ai-install-layer:claude`. Produces a private GHCR image that can be referenced in any project's `devcontainer.json`.

## Usage

```
/new-plugin-layer
```

---

## Overview

This command implements a complete plugin layer builder workflow:

1. Load standards and plugin lists
2. Fetch available plugins from 5 marketplaces
3. Interactive menu to select existing or custom builds
4. Browse plugins by marketplace or search globally
5. Hash-based deduplication (identical selections = same image)
6. Create new repo or use existing if duplicate
7. Review and confirm selections
8. Generate Dockerfile, manifest, and GitHub Actions workflow
9. Push to GitHub and trigger build

For complete details, see CLAUDE.md in build-with-claude repository.
