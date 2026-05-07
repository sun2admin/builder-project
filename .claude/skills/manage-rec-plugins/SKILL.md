---
name: manage-rec-plugins
description: Manage the recommended plugin set baked into the recommended L3 container image
usage: |
  /manage-rec-plugins

  Interactive editor for tools/build-stack/build_stack/data/recommended-plugins.json.
  This file defines which plugins are baked into the recommended L3 image
  (the default base offered by /build-stack when the user opts in).

  Operations:
    v) view current recommended set
    r) remove plugins from the recommended set
    a) add plugins via the shared selector flow (S1-S6)
    q) quit (no save unless changes already committed)
---

# /manage-rec-plugins

Curates the **recommended plugin set** — the bundle baked into the recommended
L3 image (one image, multiple plugins). `/build-stack` offers this image as
the default base when the user answers "include recommended plugins? y" at
its first prompt.

## Why This Exists

Every plugin baked into the recommended L3 saves install time and bandwidth
during devcontainer rebuild — but bloats the image and may include MCP
servers (postman plugin → postman MCP) the user doesn't want by default.
This skill lets you tune that trade-off explicitly.

Image rebuild does **not** happen here — `/manage-rec-plugins` only edits
the JSON. Image build/push lives in the upcoming `/deploy-stack` skill
(see `.claude/plans/deploy-stack.md`).

## File Edited

`tools/build-stack/build_stack/data/recommended-plugins.json`

Per-entry shape: `{marketplace, plugin, category, added_at}`. Marketplace
identified as `owner/repo` matching an entry in `marketplaces.json`.

## Add Flow

The "add" option invokes the shared selector lib
(`.claude/skills/_lib/plugin-selector.sh`) with `--exclude-recommended`
so already-recommended plugins do not appear (avoid duplicate work).
The selector returns chosen plugins, which are merged into
`recommended-plugins.json`.

## Remove Flow

Numbered list with y/N confirm per removal. Bulk-removal not supported —
keeps it deliberate, since removing a recommended plugin may surprise
existing builds that rely on it being present.

## No Auto-Rebuild

After editing, the skill prints a reminder that the recommended L3 image
must be rebuilt via `/deploy-stack` for changes to take effect in new builds.

## Related Skills

- `/manage-known-marketplaces` — manages which marketplaces are visible in the selector
- `/build-stack` — uses recommended-plugins.json to render the "include recommended? y/N" prompt
- `/deploy-stack` — *(not yet implemented)* triggers recommended L3 image rebuild
