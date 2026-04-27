---
name: Claude Code Project-Level Config Auto-Discovery
description: How Claude Code discovers project-level config (.claude/, CLAUDE.md, .mcp.json) from the workspace — no symlinks or copying needed
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Key Insight

Claude Code discovers project-level config by walking up the directory tree from the current working directory. Files committed to the repo root are found automatically — no copying, symlinking, or image-baking required.

## Project-Level Config (committed to git, lives in repo root)

```
project-repo/
├── CLAUDE.md # team instructions, loaded every session
├── CLAUDE.local.md # personal overrides, gitignored
├── .mcp.json # project MCP servers, team-shared
└── .claude/
 ├── settings.json # permissions, hooks, env vars
 ├── settings.local.json # personal overrides, gitignored
 ├── commands/ # project skills (legacy flat .md files)
 ├── skills/<name>/SKILL.md # project skills (newer format)
 ├── agents/ # subagent persona definitions
 ├── rules/ # modular instruction files
 └── hooks/ # event-driven automation
```

## User-Level Config (named volume, never committed)

```
~/.claude/
├── CLAUDE.md # personal instructions, all projects
├── settings.json # global permissions, model config
├── skills/ # personal skills, all projects
├── agents/ # personal subagents
├── plugins/ # installed plugins
└── projects/<repo-path>/
 └── memory/ # auto-memory written by Claude (NOT project-scoped)
~/.claude.json # OAuth tokens, user/local MCP, per-project trust
```

## Important: Auto-Memory Location

Auto-memory (`~/.claude/projects/<project-path>/memory/`) is user-scoped and lives in ~/.claude/ (or CLAUDE_CONFIG_DIR if set). The `<project-path>` is derived from the working directory when Claude starts (canonicalized, e.g., `/workspace/claude` → `-workspace-claude`).

Auto-memory is NOT auto-discovered from `.claude/memory/` in the project repo. However, in containerized setups where the named volume is ephemeral:
- Project memory files must be committed to the repo (e.g., `/workspace/claude/.claude/memory/`)
- init-memory.sh seeds the fresh named volume with these committed files on startup using `cp -n`
- In-session updates are preserved across restarts (not overwritten) by the `-n` flag

## Config Precedence (highest to lowest)

1. Managed (`/etc/claude-code/`)
2. Command-line arguments
3. Local (`.claude/settings.local.json`)
4. Project (`.claude/settings.json`)
5. User (`~/.claude/settings.json`)

## Why

Eliminates the need for symlinks, postStartCommand copies, or any special mounting to make project config available to Claude Code. The workspace bind mount is sufficient.