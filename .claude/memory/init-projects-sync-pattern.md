---
name: init-projects.sh Sync Pattern - Exact Files and Directories
description: Complete specification of what init-projects.sh must copy from /workspace/claude/project-*/ to ~/.claude/projects/<cwd-path>/ to emulate exactly what Claude Code does when starting in a project directory.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## What Claude Code Reads from Project Directory at Startup

When Claude starts with cwd=/workspace/claude/project-a/, it reads:
- `CLAUDE.md` (from cwd, parents, and global ~/.claude/CLAUDE.md)
- `.claude/settings.json` (project configuration)
- `.claude/settings.local.json` (local/personal overrides)
- `.claude/rules/*.md` (all rule markdown files)
- `.claude/commands/` (project-level slash commands)
- `.claude/skills/` (project skills with SKILL.md files)
- `.claude/agents/` (subagent definitions)
- `.mcp.json` (MCP server configuration)
- `.claude/memory/*.md` (committed project memory for persistence)

## What Claude Code Creates in ~/.claude/projects/<cwd-path>/

When Claude starts, it creates/uses:
- `memory/` directory (for auto-memory and session notes)
- `MEMORY.md` (created when Claude saves notes, not on first startup)
- `*.jsonl` files (session transcripts, one per session - auto-created during work)

## Exact Files init-projects.sh Must Copy

For each valid Claude project found at `/workspace/claude/project-X/`:

### 1. Copy Entire .claude Directory Structure
```
/workspace/claude/project-X/.claude/
├── settings.json              → ~/.claude/projects/<path>/.claude/settings.json
├── settings.local.json        → ~/.claude/projects/<path>/.claude/settings.local.json
├── rules/
│   └── *.md                   → ~/.claude/projects/<path>/.claude/rules/*.md (all)
├── commands/
│   └── (all files/dirs)       → ~/.claude/projects/<path>/.claude/commands/ (entire tree)
├── skills/
│   └── (all subdirs)          → ~/.claude/projects/<path>/.claude/skills/ (entire tree)
├── agents/
│   └── *.md                   → ~/.claude/projects/<path>/.claude/agents/*.md (all)
└── memory/
    └── *.md                   → ~/.claude/projects/<path>/memory/*.md (all)
```

### 2. Copy Root-Level Project Files
```
/workspace/claude/project-X/CLAUDE.md          → ~/.claude/projects/<path>/CLAUDE.md
/workspace/claude/project-X/.mcp.json          → ~/.claude/projects/<path>/.mcp.json
```

### 3. Create Memory Directory Structure
```
Create: ~/.claude/projects/<path>/memory/ (directory, empty initially)
Create: ~/.claude/projects/<path>/MEMORY.md (if not already copied from project)
```

## What NOT to Copy

- Source code files (anything not in .claude/, not CLAUDE.md, not .mcp.json)
- Session transcripts (*.jsonl files) - these are auto-created by Claude
- Generated auto-memory notes beyond MEMORY.md - these are created during work

## Directory Path Canonicalization

For `/workspace/claude/project-a/`:
- Canonicalized path: `-workspace-claude-project-a`
- Target directory: `~/.claude/projects/-workspace-claude-project-a/`

## Important Details

### Copy Flags
Use `cp -r` for directories to preserve structure
Copy entire subdirectories (rules/, commands/, skills/, agents/, memory/) not individual files

### Memory Persistence Pattern
- Project has committed memory: `/workspace/claude/project-a/.claude/memory/`
- init-projects.sh copies to named volume: `~/.claude/projects/-workspace-claude-project-a/memory/`
- On restart: memory preserved (using `-n` flag in future seeding)
- On rebuild: memory restored from git-committed files

### Verification
After copying each project, verify:
1. `.claude/` directory exists with all subdirectories
2. `CLAUDE.md` exists
3. `.mcp.json` exists (if it was in the project)
4. `memory/` directory exists with all `.md` files copied
5. Directory structure matches source exactly

## Relationship to init-memory.sh (Current Pattern)

**Current init-memory.sh (single project):**
```bash
cp -n /workspace/claude/.claude/memory/*.md ~/.claude/projects/-workspace/memory/
```

**New init-projects.sh (multi-project):**
```bash
for each /workspace/claude/project-X/:
  cp -r /workspace/claude/project-X/.claude/ ~/.claude/projects/<cwd-path>/.claude/
  cp /workspace/claude/project-X/CLAUDE.md ~/.claude/projects/<cwd-path>/CLAUDE.md
  cp /workspace/claude/project-X/.mcp.json ~/.claude/projects/<cwd-path>/.mcp.json
  mkdir -p ~/.claude/projects/<cwd-path>/memory/
  cp -n /workspace/claude/project-X/.claude/memory/*.md ~/.claude/projects/<cwd-path>/memory/
```

## Key Insight

init-projects.sh exactly emulates what Claude Code does when starting in a project directory and syncing configuration to `~/.claude/projects/<cwd-path>/`. The only difference is timing: Claude does it on-demand per project, init-projects.sh pre-populates all projects at container startup.
