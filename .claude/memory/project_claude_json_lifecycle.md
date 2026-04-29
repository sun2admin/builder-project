---
name: claude-json-lifecycle
description: .claude.json and named volume persistence — devcontainerId stability, backup behavior, re-auth conditions, and the auto-restore gap
type: project
originSessionId: 5c59a0d5-1064-4e64-9cef-f4c77d757503
---
# .claude.json and Named Volume Lifecycle

## What .claude.json Is

`/home/claude/.claude/.claude.json` is Claude Code's machine-local config file. It contains:
- OAuth auth tokens (so you don't re-authenticate every session)
- User ID, account info, org info
- Feature flag cache (`cachedGrowthBookFeatures`)
- Per-project settings (allowed tools, MCP config, trust dialogs)
- Session metrics and usage stats

It lives in the named Docker volume (`claude-code-config-${devcontainerId}`), NOT in the git repo. It must never be committed to git.

## Named Volume Persistence

Volume name: `claude-code-config-${devcontainerId}`

`devcontainerId` is a stable hash computed from the workspace folder path. It is stable across "Rebuild Container" operations in VS Code — rebuild destroys the container but leaves named volumes intact.

**Implication:** `.claude.json` survives rebuilds as long as the workspace folder path doesn't change. No re-auth required after a normal rebuild.

**When devcontainerId changes (new volume, re-auth required):**
- Workspace folder path renamed or moved
- Significant devcontainer.json changes (unclear exactly what triggers this)
- First time a completely new devcontainer workspace is created

## Backup Behavior

Claude Code creates backups of `.claude.json` at `~/.claude/backups/.claude.json.backup.<timestamp>` before modifying it (version migrations, config rewrites, etc.).

**Claude Code does NOT auto-restore from backup.** When `.claude.json` is missing but a backup exists, Claude Code prints:
```
Claude configuration file not found at: /home/claude/.claude/.claude.json
A backup file exists at: /home/claude/.claude/backups/.claude.json.backup.<timestamp>
You can manually restore it by running: cp "..." "/home/claude/.claude/.claude.json"
```
Then it proceeds with a normal first-time OAuth flow anyway. The restore is manual and optional.

If the user ignores the message and lets OAuth proceed, a new `.claude.json` is written, superseding the backup.

## "First Start" vs Rebuild Scenario

If it's truly a brand-new named volume (first ever start), there would be NO backup either. A backup existing means the volume has prior history — the `.claude.json` was lost (migration, corruption, etc.) while the backup survived. This is a rebuild/recovery scenario, not true first start.

## The Auto-Restore Gap

The current init scripts (`init-firewall.sh`, `init-ssh.sh`, `init-gh-token.sh`, `init-github-mcp.sh`, `load-projects.sh`) do not restore `.claude.json` from backup. This means:

- If `.claude.json` is missing but a backup exists, the user sees the warning and must manually run `cp` OR go through OAuth again
- Both paths work, but both are disruptive

**Proposed fix:** Add to an init script (e.g., new `init-claude-config.sh`):

```bash
if [[ ! -f "$HOME/.claude/.claude.json" ]]; then
  latest_backup=$(ls -t "$HOME/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
  if [[ -n "$latest_backup" ]]; then
    echo "Restoring Claude config from backup: $(basename "$latest_backup")"
    cp "$latest_backup" "$HOME/.claude/.claude.json"
  fi
fi
```

This would run before `postAttachCommand` starts Claude, silently restoring the backup and skipping the warning entirely.

**Why:** Not yet implemented — pending decision on whether to add to stage2/stage3 init scripts.
