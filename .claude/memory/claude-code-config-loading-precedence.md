---
name: Claude Code Config Loading Process and Precedence
description: How Claude Code loads configuration files, merges settings from multiple sources, and the complete precedence order. Covers file locations, defaults, and how variables override each other.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Config File Locations (in order of discovery)

When Claude starts with a working directory, it searches upward the directory tree and loads configuration from:

1. **Managed Settings** (highest priority, cannot be overridden)
 - `/etc/claude-code/managed-settings.json` (file-based policies)
 - Server-managed (pushed by admin)
 - MDM/OS-level policies (Windows registry, macOS defaults)

2. **CLI Arguments** (command-line flags override everything else)
 - `claude --model opus-4-7` (example: override model)
 - `--dangerously-skip-permissions` (example: override permissions)

3. **Local Settings** (user's personal overrides for this project)
 - `.claude/settings.local.json` (project-specific, gitignored)
 - `~/.claude/settings.local.json` (user-specific)

4. **Project Settings** (team-shared, committed to git)
 - `.claude/settings.json` (in project root)
 - `.claude/CLAUDE.md` (project instructions)
 - `.mcp.json` (MCP server definitions)

5. **User Settings** (global defaults for all projects)
 - `~/.claude/settings.json` (user's global settings)
 - `~/.claude/CLAUDE.md` (user's global instructions)

6. **Built-in Defaults** (lowest priority, Claude's hardcoded defaults)

## How Config Files Are Loaded and Merged

### CLAUDE.md (Instructions)
- Loaded from cwd and all parent directories up to root
- **Not merged** — all instances are concatenated and loaded together
- **Precedence:** Local CLAUDE.local.md > Project CLAUDE.md > User CLAUDE.md > Parent CLAUDE.md
- These are **instructions/context**, not settings — all are loaded

### settings.json (Configuration)
- Loaded from each scope (local, project, user, managed)
- **Merged/Overridden:** Newer sources override older ones
- For **scalar values** (strings, numbers): last value wins
- For **array values** (permissions): arrays are concatenated and deduplicated
- **Precedence:** Managed > CLI > Local > Project > User > Defaults

### Environment Variables
- Can override any setting
- Can be stored in settings.json under `env` key
- Format: `CLAUDE_CODE_<SETTING_NAME>`
- Example: `CLAUDE_CODE_AUTO_MEMORY_ENABLED=true`

## Key Settings and Their Defaults

### Model Configuration
```json
{
 "model": "claude-opus-4-7" // Default: Opus 4.6 (most capable)
}
```
Override with: `claude --model sonnet` or `CLAUDE_CODE_MODEL=sonnet`

Supported aliases: `opus`, `sonnet`, `haiku` (resolve to latest versions)
Or specify full ID: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`

### Auto-Memory Configuration
```json
{
 "autoMemoryEnabled": true, // Default: enabled
 "autoMemoryDirectory": ".claude/memory", // Default: relative to project root
 "autoMemoryMaxSize": 10485760 // Default: 10MB
}
```

### Permissions Configuration
```json
{
 "permissions": {
 "default": "ask", // Default: "ask" before using tools
 "allow": [],
 "ask": [],
 "deny": []
 }
}
```

Default behavior: Claude asks for confirmation on most tool use
Modes:
- `"ask"` — prompt before each tool use (safe, interactive)
- `"allow"` — specific tools allowed without prompt
- `"deny"` — specific tools blocked
- `--dangerously-skip-permissions` — bypass all checks (unsafe, used in automation)

### File Access
```json
{
 "allowedFileExtensions": [], // Default: empty = allow all
 "readFileLimit": null, // Default: no limit
 "maxFileSize": 104857600 // Default: 100MB
}
```

Default: Claude can read any file in cwd and subdirectories

### Other Notable Defaults
```json
{
 "autoCommit": false, // Default: don't auto-commit changes
 "enableAllProjectMcpServers": false, // Default: ask per MCP server
 "cleanup": 86400000, // Default: 1 day (delete old session transcripts)
 "autoMemory": {
 "enabled": true,
 "directory": ".claude/memory"
 }
}
```

## Practical Example: Config Resolution

Given this setup:
```
~/.claude/settings.json (User)
 → model: "claude-sonnet-4-6"

/workspace/claude/.claude/settings.json (Project)
 → model: "claude-opus-4-7"
 → autoMemoryEnabled: false

/workspace/claude/.claude/settings.local.json (Local override)
 → autoMemoryEnabled: true

$ cd /workspace/claude && claude --model haiku
```

**Resolution (highest to lowest):**
1. CLI: `--model haiku` ✓ WINS
2. Local: `autoMemoryEnabled: true` ✓ WINS (no CLI or higher)
3. Project: `model: opus` ✗ OVERRIDDEN by User
4. User: `model: sonnet` ✗ OVERRIDDEN by Project
5. Default: `permissions: ask` ✓ WINS (no override)

**Final Config Used:**
- Model: `haiku` (from CLI)
- AutoMemory: `true` (from local)
- Permissions: `ask` (from default)

## Special: CLAUDE_CONFIG_DIR Override

If environment variable `CLAUDE_CONFIG_DIR` is set:
```bash
export CLAUDE_CONFIG_DIR=/custom/path
```

All `~/.claude` paths resolve to `/custom/path` instead. This is used in build-with-claude:
```bash
CLAUDE_CONFIG_DIR=/home/claude/.claude
```

This explicitly tells Claude to use the named volume location, not the default home directory.

## Settings Schema and Validation

Official JSON schema available at:
`https://json.schemastore.org/claude-code-settings.json`

Use in VS Code/Cursor for autocomplete and validation:
```json
{
 "$schema": "https://json.schemastore.org/claude-code-settings.json",
 "model": "claude-opus-4-7"
}
```

## How This Applies to Multi-Project Workspaces

In build-with-claude scenario with `/workspace/` as root and `/workspace/claude/` as project:

1. **When Claude starts with cwd=/workspace/claude:**
 - Searches: `/workspace/claude/.claude/` → `/workspace/.claude/` → `~/.claude/`
 - Loads: project settings, then user settings, then defaults
 - Creates project entry: `~/.claude/projects/-workspace-claude/`

2. **If you had /workspace/project-b:**
 - Would need separate `.claude/settings.json` in `/workspace/project-b/.claude/`
 - Starting from `/workspace/project-b` would load that project's config
 - Creates separate entry: `~/.claude/projects/-workspace-project-b/`

3. **No collision because:**
 - Config is loaded from cwd (separate per project)
 - Memory stored in `~/.claude/projects/<cwd-path>/` (separate per working directory)
 - Each project can have completely different settings, instructions, permissions