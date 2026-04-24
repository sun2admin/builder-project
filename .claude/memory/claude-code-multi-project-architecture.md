---
name: Claude Code Multi-Project Architecture and Session Management
description: How Claude Code fundamentally handles multiple projects - single-project-per-session design, /resume command for switching, global context in ~/.claude, and why copying all projects to ~/.claude/projects/ enables seamless multi-project support without explicit project selection.
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Core Architecture: Single-Project-Per-Session Design

Claude Code is **fundamentally designed for one project per session**, not multiple simultaneous projects in one context.

**Session Context:**
- Each session has one cwd (working directory)
- Each session loads one project's CLAUDE.md and .claude/ config
- Sessions are indexed by directory path: `~/.claude/projects/<cwd-path>/`
- Session history and auto-memory are stored per-project under that path

**Example:**
```
cwd=/workspace/project-a → reads from ~/.claude/projects/-workspace-project-a/
cwd=/workspace/project-b → reads from ~/.claude/projects/-workspace-project-b/
```

## Switching Between Projects: /resume Command

Users don't specify "which project is active" upfront. Instead:

1. **User types `/resume`**
   - Opens interactive session picker
   - Shows ALL available sessions from ALL projects
   - Lists projects with their paths

2. **User selects a project**
   - Claude switches to that project's cwd
   - Loads that project's CLAUDE.md and .claude/ config
   - Accesses that project's memory and session history

3. **Work on selected project**
   - Claude now operates in that project context
   - Can use /resume again anytime to switch

**Key behavior:**
- /resume can browse sessions across different project directories (though with recent regressions in v2.1.98+)
- Sessions are NOT limited to current directory — Claude can find and resume any project's sessions
- Each /resume switches the effective cwd context

## Global Context: ~/.claude Without a Project

When Claude starts without an explicit project cwd:

**Global ~/.claude files available everywhere:**
- `~/.claude/CLAUDE.md` — global instructions applied to all projects
- `~/.claude/commands/` — global slash commands available in all projects
- `~/.claude/agents/` — personal agent definitions available everywhere
- `~/.claude/settings.json` — global settings applied universally

**Example use case:**
```
$ cd ~  (or /workspace without project-specific config)
$ claude
→ Claude starts in "global" mode using ~/.claude/ context
→ No project-specific CLAUDE.md, but global settings applied
→ User can type /resume to switch to a specific project
```

## Multi-Project Setup: Copy All Projects to ~/.claude/projects/

**The approach:**
```
Source (in git repo):
  /workspace/claude/
    ├── project-a/.claude/
    ├── project-b/.claude/
    └── project-c/.claude/

Copied to named volume:
  ~/.claude/projects/
    ├── -workspace-project-a/.claude/
    ├── -workspace-project-b/.claude/
    └── -workspace-project-c/.claude/
```

**How it works:**
1. postAttachCommand: `claude` (no explicit cd to project)
2. workspaceFolder: `/workspace` (has .git, avoids hang bug)
3. Claude starts from /workspace in global context
4. User types `/resume`
5. /resume picker shows all three projects
6. User selects project-a
7. Claude loads project-a context from `~/.claude/projects/-workspace-project-a/`
8. User works on project-a

**Benefits:**
- ✓ Single startup command (no per-project .devcontainer)
- ✓ /workspace has .git (avoids non-git directory hang)
- ✓ All projects accessible via /resume
- ✓ Clean global context until user selects project
- ✓ No need to change directory before starting Claude

## Implications for /build-project Skill

**Multi-project scaffold would include:**

1. **init-memory.sh** — copies all projects' .claude/memory/ to ~/.claude/projects/<path>/memory/
2. **Root-level /workspace/.claude/** — optional global config for all projects
3. **Root-level /workspace/CLAUDE.md** — optional global instructions
4. **Per-project /workspace/project-*/.claude/** — project-specific config
5. **Single postAttachCommand** — `claude` (no explicit cd)

**Structure:**
```
/workspace/                        ✓ git repo (.git exists)
  ├── .devcontainer/
  │   └── devcontainer.json       (workspaceFolder=/workspace, postAttach: claude)
  ├── .claude/                    (optional global config)
  ├── CLAUDE.md                   (optional global instructions)
  └── claude/
      ├── project-a/
      │   ├── .claude/            (project-specific)
      │   └── CLAUDE.md
      ├── project-b/
      │   ├── .claude/
      │   └── CLAUDE.md
      └── project-c/
          ├── .claude/
          └── CLAUDE.md
```

**On container start:**
1. init-memory.sh copies all projects' configs to ~/.claude/projects/<path>/
2. Claude starts from /workspace (global context)
3. User uses /resume to select project
4. Claude switches to project context

## Why This Works Without Explicit Project Selection Config

1. **Claude's /resume is built-in** — no config needed
2. **Projects are discovered automatically** — /resume scans ~/.claude/projects/
3. **Working directory determines context** — when user selects a project, cwd changes
4. **Session history is indexed by path** — previous work is preserved per-project

No manifest, no registry, no "active project" file needed — Claude's session indexing handles it.
