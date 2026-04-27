# Dev Containers — Claude Code Authentication & Volume Strategy

## Claude Code Authentication in Containers

- Claude Code uses two files for auth state:
 - `~/.claude/.credentials.json` — OAuth access/refresh tokens
 - `~/.claude/.claude.json` — session state including `hasCompletedOnboarding`, `oauthAccount`, `userID`
- Both files must be present for Claude Code to skip the sign-in flow
- `hasCompletedOnboarding: true` is only written by Claude Code itself after the user completes onboarding — it cannot be pre-seeded externally because Claude Code overwrites `.claude.json` on first run (generating a new `userID`, `firstStartTime`, etc.)
- OAuth tokens auto-refresh but can sometimes fail, requiring manual re-authentication
- The firewall must allow HTTPS (port 443) for token validation against `claude.ai` and `api.anthropic.com`

## Claude Code Volume Strategy

- **Per-container volumes** (`claude-code-config-${devcontainerId}`): each workspace/container gets isolated auth state. User signs in once per new container. Safe for simultaneous containers. Sign-in persists across rebuilds of the same workspace.
- **Fixed shared volume** (`claude-code-config`): all containers share auth state. Sign in once globally. Risk of `.claude.json` write corruption and token refresh race conditions when multiple containers run simultaneously.
- Recommended for multi-container setups: per-container volumes