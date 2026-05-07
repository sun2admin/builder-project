# Plan Note: Settings Placement Review

**Status:** Open. Defer until current build-stack work is past task 25.

## Context

May 7 2026: discovered context-warn hook + statusline customizations were initially split between project `.claude/` (committable) and user `~/.claude/` (named-volume-only). Volume-loss risk made the split fragile. Migrated everything to project per the new feedback rule:

> All settings, hooks, statuslines go to project, never user / named-volume.

Ref: `memory/feedback-settings-go-to-project.md`.

## What's currently in the project (post-migration)

- `.claude/hooks/session-start.sh`
- `.claude/hooks/context-warn.sh` (UserPromptSubmit, ≥250K warn, ≥400K critical)
- `.claude/hooks/statusline.sh` (combined caveman badge + context meter, color-graded)
- `.claude/settings.json` keys: `env`, `hooks` (SessionStart + UserPromptSubmit), `permissions`, `autoCompactEnabled: true`, `autoCompactWindow: 300000`, `statusLine`

## Open questions to resolve later

1. **Project vs Layer image** — `autoCompactEnabled` + `autoCompactWindow` + `statusline.sh` are not builder-project–specific. Should they move upstream into Layer 2 or Layer 3 build (e.g., copied into `/etc/skel/.claude/` or seeded via the existing plugin-cache pattern) so every container off those images inherits without per-project duplication? Trade-off: rebuild cadence (Layer 2/3 changes are heavy) vs reproducibility for downstream projects.
2. **Hook/script defaults vs per-project tuning** — if these move to a Layer image, leave thresholds (`CONTEXT_WARN_THRESHOLD`, `CONTEXT_HARD_THRESHOLD`, `CONTEXT_WINDOW`) overridable via env in project settings, so a noisy project can lower the bar.
3. **Layer 4 devcontainer override path** — does the Layer 4 devcontainer template need to surface the hooks/statusline location explicitly, or is the project `.claude/` discovery sufficient?
4. **Reference-only items** — anything that should stay user-level personal (theme, plugin enablement, OAuth) needs an explicit allowlist so future placements don't drift back into `~/.claude/`.

## Decision protocol

Pick one of three end-state placements per item:

| Placement | When |
|---|---|
| Project `.claude/` (current) | Project-specific or builder-project-as-reference |
| Layer 2/3 image (baked) | Stack-wide default that should ship with any AI-CLI container |
| User `~/.claude/` (named volume) | Truly personal preference; document why it can't be project |

## Resume conditions

Pick this back up when:
- build-stack tasks 10–11 + plugin_selections install gap are closed, or
- a new project repo is being built off this stack and the duplication cost becomes real.
