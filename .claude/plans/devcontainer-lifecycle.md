---
name: devcontainer-lifecycle
description: Reference for .claude.json lifecycle, named volume persistence, devcontainerId stability, and backup/restore behavior
---

# Devcontainer Lifecycle Reference

## Named Volume Persistence

The Claude config volume is named `claude-code-config-${devcontainerId}`. It contains:
- `~/.claude/.claude.json` — auth tokens, account info, per-project settings, feature flag cache
- `~/.claude/projects/<canonical-path>/memory/` — auto-memory written during sessions
- `~/.claude/backups/` — Claude Code backups of `.claude.json`

`devcontainerId` is a stable hash of the workspace folder path. It does NOT change on "Rebuild Container" — named volumes survive rebuilds.

| Event | Named volume | .claude.json | Re-auth required? |
|---|---|---|---|
| Container restart | Persists | Persists | No |
| Rebuild Container | Persists | Persists | No |
| New workspace path | New volume created | Missing | Yes |
| First ever start | New (empty) | Missing | Yes |

**devcontainerId changes when:** workspace folder path changes, or a new devcontainer workspace is created from scratch.

## .claude.json

Machine-local Claude Code config. Must never be committed to git. Contains OAuth tokens, user/org IDs, feature flags, per-project trust settings.

**Location:** `/home/claude/.claude/.claude.json` (in named volume)

**Missing .claude.json behavior:** Claude Code prints a warning, then proceeds with a first-time OAuth flow. If a backup exists at `~/.claude/backups/.claude.json.backup.<timestamp>`, it shows the manual `cp` restore command — but does NOT auto-restore. The user either runs `cp` manually or goes through OAuth.

## Backup Behavior

Claude Code creates backups at `~/.claude/backups/.claude.json.backup.<timestamp>` before modifying the file (version migrations, config rewrites). These backups are in the named volume, so they persist across rebuilds.

**Distinguishing "true first start" from "rebuild with lost config":**
- True first start: no `.claude.json` AND no backups (volume is empty)
- Lost config after prior run: no `.claude.json` BUT backups exist

## Auto-Restore Gap (Proposed Fix)

Current init scripts do not restore `.claude.json` from backup. To close this gap, add to `postStartCommand` (e.g., in a new `init-claude-config.sh`):

```bash
if [[ ! -f "$HOME/.claude/.claude.json" ]]; then
  latest_backup=$(ls -t "$HOME/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
  if [[ -n "$latest_backup" ]]; then
    echo "Restoring Claude config from backup: $(basename "$latest_backup")"
    cp "$latest_backup" "$HOME/.claude/.claude.json"
  fi
fi
```

Run this before the `postAttachCommand` starts Claude — it silently restores auth, skipping the warning and re-auth flow entirely.

**Status:** Not yet implemented. Lives in `build-with-claude-stage2` init scripts when added.

## Memory Seeding vs .claude.json

These are separate concerns handled by separate mechanisms:

| Artifact | Location | Mechanism |
|---|---|---|
| `.claude.json` | Named volume root | OAuth on first start; backup restore (manual or init script) |
| `memory/*.md` | Named volume `projects/` dir | `load-projects.sh` seeds from git with `cp -n` |
| Skills, commands, settings | Bind-mounted repo | Read directly from repo via cwd walk-up; no seeding needed |

`load-projects.sh` only handles memory seeding — it does not touch `.claude.json`.
