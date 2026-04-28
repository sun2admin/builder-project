---
name: Claude Code File Write Locations — Definitive Reference
description: Exactly where each file type is written during a session. Critical for designing correct load/sync scripts. Confirmed against official Anthropic docs and live container observation.
type: project
---

## The Core Rule

Claude Code reads project config directly from the **project repo on the bind mount** (by walking up from cwd). It does NOT read from `~/.claude/projects/<path>/.claude/`. The `~/.claude/projects/` directory is for session state only — not a config mirror.

## Where Each File Type Is Written

| File | Written by | Written to | Portable? |
|---|---|---|---|
| Skills (`.claude/skills/`) | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| Commands (`.claude/commands/`) | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| Agents (`.claude/agents/`) | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| Rules (`.claude/rules/`) | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| `settings.json` | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| `CLAUDE.md` | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| `.mcp.json` | Claude's Write/Edit tools | **Project repo** (bind mount) | ✓ Yes — committed to git |
| Auto-memory (`memory/*.md`) | Claude Code internally | `~/.claude/projects/<path>/memory/` | ✗ No — machine-local only |
| `settings.local.json` | Claude Code internally | `.claude/settings.local.json` in **project repo** (auto-gitignored) | ✗ No — gitignored |
| Session transcripts (`.jsonl`) | Claude Code internally | `~/.claude/projects/<path>/` | ✗ No — never committed |

## Proof from Live Observation

Checked inodes of `settings.json` in both locations:
- Repo copy: inode `12687` at `/workspace/claude/builder-project/.claude/settings.json` (modified today — Claude wrote here)
- Projects dir copy: inode `3440122` at `~/.claude/projects/workspace-claude-builder-project/.claude/settings.json` (stale seed from yesterday)

**They are separate files. Claude wrote to the repo, not the projects dir.**

## Auto-Memory: Official Anthropic Statement

> *"Auto memory is machine-local. All worktrees and subdirectories within the same git repository share one auto memory directory. Files are not shared across machines or cloud environments."*

Storage path: `~/.claude/projects/<project>/memory/`

The `<project>` identifier is derived from the **git repository root** — so all subdirectories within the same repo share one memory directory.

## Canonical Path Format

For `/workspace/claude/builder-project` (git repo root):
```bash
echo "/workspace/claude/builder-project" | sed 's|^/||;s|/|-|g'
# → workspace-claude-builder-project
```

Note: No leading dash. Older scripts that didn't strip the leading `/` before replacing produced `-workspace-...` (with leading dash) — that format is incorrect.

## What `~/.claude/projects/<path>/.claude/` Actually Is

This directory is populated by `load-projects.sh` seeding — it is NOT written by Claude Code itself. Claude Code does not read from it for config. It reads config from the project repo (cwd walk-up). The `.claude/` copy in the projects dir is a stale seed artifact that serves no runtime purpose for skills, commands, agents, rules, or settings.

**The only files that genuinely belong in `~/.claude/projects/<path>/` are:**
- `memory/` — auto-memory Claude writes and reads during sessions
- `*.jsonl` — session transcripts (auto-created, never synced)

## Implications for load-projects.sh

**Do NOT seed**: `.claude/skills/`, `.claude/commands/`, `.claude/agents/`, `.claude/rules/`, `.claude/settings.json` into `~/.claude/projects/<path>/.claude/` — Claude never reads them from there.

**Do seed**: `memory/*.md` → `~/.claude/projects/<path>/memory/` using `cp -n` (no-overwrite to preserve in-session writes on restart).

## Implications for sync-prj-repos-memory

**Do NOT sync back**: `.claude/` from `~/.claude/projects/<path>/.claude/` to the repo — that copy is stale and would overwrite newer repo files.

**Do sync back**: `~/.claude/projects/<path>/memory/*.md` → `<repo>/.claude/memory/` then `git add .claude/memory/ && git commit && git push`.

**For skills/commands/agents etc**: They are already in the repo (Claude wrote them there). Just run `git add -A && git commit && git push` to capture any new/modified files.

## settings.local.json Special Case

Claude Code writes `settings.local.json` to `.claude/settings.local.json` in the **project repo** and automatically adds it to `~/.config/git/ignore`. It contains machine-local state (MCP server enablement, personal permission overrides). It should NOT be committed. The copy found at `~/.claude/projects/<path>/.claude/settings.local.json` is a stale artifact from earlier load-projects.sh seeding that copied the entire `.claude/` tree.
