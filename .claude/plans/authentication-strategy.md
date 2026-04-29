---
name: authentication-strategy
description: Claude Code authentication in devcontainers — why first login is required, how auth persists across rebuilds, what breaks when devcontainerId changes, and future improvement options
---

# Claude Code Authentication Strategy

## Why Login Is Required on First Start

When a devcontainer is created for the first time, the named volume is brand new and empty. There is no `~/.claude/.credentials.json` and no `~/.claude/.claude.json`. Claude Code has no stored auth state, so it initiates a browser-based OAuth flow.

**This is the only unavoidable login.** All subsequent rebuilds of the same container do not require re-authentication — as long as the named volume survives.

## Why Subsequent Rebuilds Do Not Require Re-auth

The named volume is keyed by `devcontainerId`:

```
claude-code-config-${devcontainerId}
```

`devcontainerId` is a stable hash derived from the workspace folder path. "Rebuild Container" in VS Code destroys and recreates the container but leaves named volumes intact. The volume — and all auth state inside it — survives.

| Event | Named volume | Auth state | Re-auth? |
|---|---|---|---|
| Container restart | Persists | Persists | No |
| Rebuild Container | Persists | Persists | No |
| Workspace path renamed/moved | New volume (old orphaned) | Missing | Yes |
| New devcontainer workspace | New volume (empty) | Missing | Yes |
| First ever start | New volume (empty) | Missing | Yes |

## What Auth State Looks Like

Claude Code stores authentication across two files, both inside the named volume:

| File | Location | Contains |
|---|---|---|
| `.credentials.json` | `~/.claude/.credentials.json` | OAuth access token + refresh token |
| `.claude.json` | `~/.claude/.claude.json` | Account UUID, email, org UUID, onboarding state, feature flag cache, per-project settings |

**Both files are required to skip re-auth.** Persisting `.credentials.json` alone is not sufficient — without `.claude.json`, Claude Code treats the session as a fresh install and prompts for login regardless of valid credentials. This was confirmed in community research (field-notes-public issue #10).

Neither file is encrypted. Both are plain JSON. Neither should ever be committed to git or baked into container images — they contain PII (email, org UUID, account UUID) and are user-account-specific.

## When devcontainerId Changes

If the workspace folder path changes or a new devcontainer workspace is provisioned, a new empty volume is created. The old volume with its auth state is orphaned. Claude Code will require re-authentication.

**Current behavior:** The user must complete a browser OAuth flow on first start of the new container. There is no automation to carry auth forward.

## Auth Precedence (Official Anthropic Docs)

Claude Code checks credentials in this order and uses the first one it finds:

1. Cloud provider env vars (`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_USE_FOUNDRY`)
2. `ANTHROPIC_AUTH_TOKEN` env var — bearer token for LLM gateway/proxy routing
3. `ANTHROPIC_API_KEY` env var — direct API key from Claude Console
4. `apiKeyHelper` script — dynamic/rotating credentials from a vault
5. `CLAUDE_CODE_OAUTH_TOKEN` env var — long-lived token from `claude setup-token`
6. Subscription OAuth from `~/.claude/.credentials.json` — default for Pro/Max/Teams/Enterprise

## Future Improvement Options

### Option A: `CLAUDE_CODE_OAUTH_TOKEN` (Recommended)

Anthropic's official solution for headless/CI environments. Run `claude setup-token` once on any authenticated host:

```bash
claude setup-token
# Walks through OAuth, prints a 1-year token. Does NOT save it anywhere.
```

Store the token as a container secret at `/run/credentials/claude_oauth_token` (following the existing credential file pattern). Add a new `init-claude-config.sh` init script:

```bash
#!/usr/bin/env bash
# init-claude-config.sh — inject Claude OAuth token before Claude starts

TOKEN_FILE="/run/credentials/claude_oauth_token"

if [[ -f "$TOKEN_FILE" ]]; then
  token=$(cat "$TOKEN_FILE")
  # Write to ~/.profile so postAttachCommand's bash --login sources it
  echo "export CLAUDE_CODE_OAUTH_TOKEN='$token'" >> "$HOME/.profile"
  chmod 600 "$HOME/.profile"
  echo "Claude OAuth token loaded"
fi
```

**Behavior:** Claude Code picks up `CLAUDE_CODE_OAUTH_TOKEN` at priority 5, above the stored subscription credentials. No browser login required — even on a brand-new volume with a changed `devcontainerId`.

**Token properties:**
- Valid for 1 year
- Scoped to inference only (cannot establish Remote Control sessions)
- Tied to your Claude Pro/Max/Teams/Enterprise subscription
- Does not work with `--bare` mode (use `ANTHROPIC_API_KEY` instead)

**Renewal:** Must be regenerated annually. Can be rotated by updating the credential file and rebuilding.

---

### Option B: Auto-restore `.claude.json` from Backup

Claude Code creates timestamped backups at `~/.claude/backups/.claude.json.backup.<timestamp>` before modifying the config file. These backups survive rebuilds (they're in the named volume). If `.claude.json` is lost while backups remain, Claude Code prints a manual restore command but does NOT auto-restore.

Add to an init script (e.g., `init-claude-config.sh`):

```bash
if [[ ! -f "$HOME/.claude/.claude.json" ]]; then
  latest_backup=$(ls -t "$HOME/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
  if [[ -n "$latest_backup" ]]; then
    echo "Restoring Claude config from backup: $(basename "$latest_backup")"
    cp "$latest_backup" "$HOME/.claude/.claude.json"
  fi
fi
```

**Limitation:** Only works when the named volume still contains backups. Does not help when `devcontainerId` changes (new empty volume, no backups). This closes the backup-restore gap but not the devcontainerId-change gap.

---

### Option C: Minimal Stub + Persisted `.credentials.json`

Community-validated approach. Persist only `.credentials.json` in a Docker volume. On each rebuild, write a minimal `.claude.json` stub:

```json
{"hasCompletedOnboarding": true, "installMethod": "native"}
```

This skips the onboarding wizard while keeping settings fresh each rebuild. Auth tokens in `.credentials.json` are reused.

**Limitation:** Requires the `.credentials.json` volume to survive. Still fails on `devcontainerId` change unless the credentials volume is shared across workspace paths.

---

## Recommended Approach for This Stack

**Combine Option A + Option B:**

1. **Option A** handles the `devcontainerId`-change case and any new machine/workspace — the 1-year token provides auth regardless of volume state.
2. **Option B** handles the narrower case of `.claude.json` loss within the same volume (e.g., after a Claude Code version migration that corrupts config).

Together they cover all failure modes without storing sensitive auth files in git or images.

### Implementation Steps

1. Generate `CLAUDE_CODE_OAUTH_TOKEN` on authenticated host: `claude setup-token`
2. Store token at `/run/credentials/claude_oauth_token` (bind-mounted, chmod 600)
3. Add `init-claude-config.sh` to `postStartCommand` in `devcontainer.json` — runs before Claude starts
4. Script combines both Options A and B: token injection first, backup restore fallback second
5. Update `build-with-claude-stage2` (or Stage 3 when applicable) to include the new init script

### What Does NOT Change

- Named volume mount (`claude-code-config-${devcontainerId}`) stays — it protects auth on normal rebuilds without needing the token
- `.credentials.json` and `.claude.json` remain in the named volume only — never in git or images
- Backup files in `~/.claude/backups/` remain in the named volume only — not encrypted, contain PII, not portable

## Files Involved

| File | Location | Role |
|---|---|---|
| `init-claude-config.sh` | `scripts/` in build-with-claude repo | New init script: injects token + restores backup |
| `devcontainer.json` | `.devcontainer/` | Add `init-claude-config.sh` to `postStartCommand` |
| `/run/credentials/claude_oauth_token` | Bind-mounted secret | Long-lived OAuth token (1 year) |
| `~/.claude/.credentials.json` | Named volume | OAuth access + refresh tokens (written by Claude) |
| `~/.claude/.claude.json` | Named volume | Account info + settings (written by Claude) |
| `~/.claude/backups/` | Named volume | Claude Code auto-backups of `.claude.json` |

## Status

- [x] Named volume mount in place (`claude-code-config-${devcontainerId}`)
- [ ] `init-claude-config.sh` not yet written
- [ ] `CLAUDE_CODE_OAUTH_TOKEN` not yet provisioned as container secret
- [ ] Backup auto-restore not yet implemented
