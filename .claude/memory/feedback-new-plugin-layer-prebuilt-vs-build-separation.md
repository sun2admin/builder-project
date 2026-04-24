---
name: new-plugin-layer should separate prebuilt definitions from built images
description: Architectural issue - prebuilt names and built repo names are conflating two separate concepts
type: feedback
originSessionId: 0ff12816-d740-4e1d-bfd5-4f53f2a05a1d
---
**Issue:** standards.json currently mixes prebuilt definitions with actual built images. When you create a prebuilt named "build-repo-plugins" in plugin-lists.json, later building that prebuilt creates a GitHub repo. But naming the repo "build-repo-plugins" conflicts with the prebuilt definition name in standards.json.

**Why:** Prebuilts (plugin combinations) and builds (actual repos/images) are separate concepts:
- One prebuilt can generate multiple built images (with marketplace customization)
- One built image can match multiple prebuilts (if plugin sets are identical)

**How to apply:** Separate the two:
- **plugin-lists.json**: Prebuilt definitions (what plugins to include) — "build-repo-plugins" is fine here
- **standards.json**: Built images only (actual repos/Docker images) — built repos should use hash-based or user-chosen names, not prebuilt names

This allows prebuilts and builds to coexist without naming collisions. A prebuilt named "build-repo-plugins" in plugin-lists.json can build to a repo named "claude-plugins-a7f3d2e8" in standards.json.
