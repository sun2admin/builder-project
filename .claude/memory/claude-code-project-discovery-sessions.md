---
name: Claude Code Project Discovery and Session Management
description: How Claude Code discovers projects, manages state across restarts, and differences in containerized environments. Covers working directory, .claude folder, memory persistence, and ~/.claude/projects structure.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Core Project Discovery Mechanism

**Working Directory is the Key:**
Claude Code identifies projects based on the **current working directory (cwd)** when Claude is started. When you run `claude` command, it uses:
1. The current terminal working directory as the starting point
2. Recurses UP the directory tree (not down) looking for project config files
3. Reads CLAUDE.md, .claude/, .mcp.json from the first matching directory or parent directories

**Important:** Claude Code reads CLAUDE.md and config files recursively up the tree, but the working directory sets the initial context and scoping boundary.

## Project Config Files (What Claude Looks For)

When Claude starts in a cwd, it searches upward for:
- `CLAUDE.md` — project-level persistent instructions
- `.claude/` directory — project-scoped config, skills, agents, rules
- `.mcp.json` — MCP server configuration
- `CLAUDE.local.md` — personal overrides (gitignored)
- `.claude/settings.local.json` — personal settings overrides (gitignored)

**If found:** Claude loads this as project config and uses it across all sessions
**If not found:** Claude falls back to user-level config in `~/.claude/`

## Session State and Memory Storage

### Auto-Memory Directory
Auto-memory is stored at: `~/.claude/projects/<project-identifier>/memory/`

The `<project-identifier>` is derived from the **git repository root** path, canonicalized:
- Strip leading `/`, replace remaining `/` with `-`
- `/workspace/claude` → `workspace-claude` (no leading dash)

When Claude starts with cwd=/workspace/claude:
- It creates/uses `~/.claude/projects/workspace-claude/` for session data
- Auto-memory writes to `~/.claude/projects/workspace-claude/memory/`
- Session transcripts stored in `~/.claude/projects/workspace-claude/<session-id>.jsonl`

### What Gets Persisted in ~/.claude/projects/
1. **Auto-memory files** — notes Claude writes when learning preferences/corrections
2. **Session transcripts** — conversation history in .jsonl format (one per session)
3. **Session summaries** — structured markdown at `<project-id>/<session-id>/session-memory/summary.md`
4. **Configuration state** — project-specific overrides and preferences

### What Does NOT Get Persisted
- OAuth tokens (stored separately in ~/.claude.json)
- Installed plugins (stored in ~/.claude/plugins/)
- User-level instructions (stored in ~/.claude/CLAUDE.md)

## Startup and Restart Behavior

### On Startup (Fresh Container/Machine)
1. User/CI sets cwd to project directory (e.g., `cd /workspace/claude`)
2. User runs `claude` command
3. Claude detects cwd = `/workspace/claude`
4. Claude walks up directory tree from `/workspace/claude` looking for config
5. Finds `/workspace/claude/.claude/`, `/workspace/claude/CLAUDE.md`
6. Loads project config from there
7. Creates or updates `~/.claude/projects/workspace-claude/` directory
8. **No memory is pre-seeded** — auto-memory from previous sessions already lives in `~/.claude/projects/workspace-claude/memory/`

### On Restart (Container Restart, Same Session)
1. Same cwd set (postAttachCommand does this: `cd /workspace/claude && claude ...`)
2. Claude starts from same working directory
3. Claude loads the SAME project config (hasn't changed)
4. Claude accesses the SAME `~/.claude/projects/workspace-claude/` that was persisted
5. Previous session's auto-memory is still there
6. Previous session transcripts are still there
7. Session continues seamlessly (if not starting new session)

### On Rebuild (Container Image Rebuild, New devcontainerId)
1. If named volume is tied to `devcontainerId`: named volume gets FRESH (previous state lost)
2. But project config in `/workspace/claude/.claude/` is on bind mount (survives rebuild)
3. This is why we need load-projects.sh: to seed fresh named volume with project memory from git-committed files

## How Containers Differ From Local Setups

### Local Setup
- cwd and ~/.claude live on same filesystem (host machine)
- Everything is persistent by default
- Switching between projects = `cd /path/to/project-a` then `cd /path/to/project-b`
- Each project has its own `~/.claude/projects/<path>/` entry automatically

### Containerized Setup
- cwd lives in **bind-mounted volume** (persists across restarts and rebuilds)
- `~/.claude/` lives in **named volume** (persists across restarts, fresh on rebuild)
- Switching between projects = would need to `cd` within container and have multiple projects in `/workspace/`
- If named volume gets wiped on rebuild, memory must be **re-seeded from git-committed files**

**Critical Pattern:** load-projects.sh bridges the gap:
```bash
# Seed only memory/*.md — all other config read from repo via cwd walk-up
mkdir -p ~/.claude/projects/workspace-claude/memory
cp -n /workspace/claude/.claude/memory/*.md \
  ~/.claude/projects/workspace-claude/memory/ 2>/dev/null || true
```

This copies project memory from git-committed location into the fresh named volume. The `cp -n` (no-overwrite) ensures in-session updates aren't blown away on restart.

## ~/.claude/projects Directory Structure Explained

```
~/.claude/projects/
├── workspace-claude/             # Project: /workspace/claude (git repo root)
│   ├── memory/                   # Auto-memory (persisted in named volume)
│   ├── 5521fc77-xxxx.jsonl       # Session transcript file
│   ├── a924aeb1-xxxx.jsonl       # Another session transcript
│   └── [more session data]
│
└── workspace-claude-builder-project/  # Would exist if builder-project was a separate git repo
    └── memory/
```

**Note:** All subdirectories of the same git repo share one project entry. The identifier is derived from the git repo root, not the specific subdirectory.

## CLAUDE_CONFIG_DIR Environment Variable

If set, this env var overrides where Claude looks for config:
```bash
export CLAUDE_CONFIG_DIR="/custom/path"
```
Then all `~/.claude` references resolve to `/custom/path` instead.

build-with-claude sets: `CLAUDE_CONFIG_DIR=/home/claude/.claude` — explicitly pointing to the named volume location.

## Key Takeaway for Multi-Project Workspaces

If you want multiple projects in one workspace (e.g., `/workspace/project-a`, `/workspace/project-b`):

1. Each project needs its own `.claude/` directory with separate config
2. Each project needs to be started with a separate `cd /workspace/project-X` before `claude` runs
3. Claude automatically creates separate `~/.claude/projects/workspace-project-x/` entries
4. Each project maintains separate memory, session history, config
5. No risk of collision or cross-contamination (working directory scoping handles this)

The key is: **one cwd per Claude session = one project entry in ~/.claude/projects/**.
