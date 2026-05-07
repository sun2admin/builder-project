---
name: manage-known-marketplaces
description: Manage the marketplaces.json registry of plugin marketplace repos used by /build-stack and /manage-rec-plugins
usage: |
  /manage-known-marketplaces

  Interactive menu to add, list, or remove marketplace entries in
  tools/build-stack/build_stack/data/marketplaces.json.

  Operations:
    a) Add — prompts for owner/repo, validates via `gh repo view`,
       requires .claude-plugin/marketplace.json present in the repo
    l) List — shows registered marketplaces with default flag
    r) Remove — numbered list, confirms before deletion
    q) Quit
---

# /manage-known-marketplaces

Manages the **marketplaces.json** registry — the list of plugin marketplace
repos that `/build-stack` and `/manage-rec-plugins` show in their selector.

## Why This Exists

The plugin selector flow (S1) starts by asking the user to pick a marketplace.
That list comes from `marketplaces.json`. This skill is the only sanctioned
way to mutate that file — it validates new entries against GitHub before
writing, preventing typos and dangling references.

## Validation Rules

Every add operation runs two checks before persisting:

| Check | Tool | Failure |
|---|---|---|
| Repo exists + accessible | `gh repo view <owner>/<repo>` | abort, no write |
| `.claude-plugin/marketplace.json` exists in repo root | `gh api repos/<o>/<r>/contents/.claude-plugin/marketplace.json` | abort, no write |

## Defaults

If `marketplaces.json` is missing or empty, the skill seeds:
`anthropics/claude-plugins-official` (default: true).

## Schema

See `tools/build-stack/build_stack/data/marketplaces.json` for the
authoritative shape. Per-entry fields: `owner`, `repo`, `marketplace_name`
(from the upstream marketplace.json `name` field), `added_at`, optional
`default: true`.

## No Edit Op

To change an entry, remove and re-add. Keeps the implementation small and
avoids partial-state bugs.
