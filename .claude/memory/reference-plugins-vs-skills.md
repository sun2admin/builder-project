---
name: Plugins vs Skills distinction
description: Claude plugins are different from Claude Code skills (slash commands). How to verify each.
type: reference
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Plugins vs Skills

**Claude Plugins** (e.g., `code-review@claude-plugins-official`):
- Installed in `/opt/claude-custom-plugins/` and other seed directories
- Seeded via `CLAUDE_CODE_PLUGIN_SEED_DIR` environment variable
- Used internally by Claude when executing tasks
- Verified with: `claude plugin list`
- Not available as slash commands

**Claude Code Skills** (e.g., `/review`, `/security-review`, `update-config`):
- Slash commands or skills that show up in `/help`
- Invoked interactively by the user or agents
- Different from plugins
- Verified with: `/help` or listing available skills

## Verifying Prebuilt Plugins

To verify that plugins from a prebuilt list (e.g., `build-repo-plugins`) are available:

```bash
claude plugin list | grep -E "code-review|code-simplifier|pr-review-toolkit|feature-dev|commit-commands|security-guidance|postman|document-skills"
```

Or just:

```bash
claude plugin list
```

All 19 plugins from "build-repo-plugins" should show `✓` status when listed.
