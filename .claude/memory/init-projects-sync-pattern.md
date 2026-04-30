---
name: load-projects.sh Sync Pattern
description: What load-projects.sh copies from project repos into ~/.claude/projects/ to seed memory and config at container start
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## What load-projects.sh Does

`load-projects.sh` (lives in `layer4-devcontainer/scripts/`) runs at container start via `postStartCommand`. It:
1. Clones the specified project repo into `/workspace/claude/<name>`
2. Seeds memory from the repo into the named volume
3. Writes the live project path to `~/live-project`

## Memory Seeding Pattern

```bash
# cp -n preserves any in-session writes already in the named volume
cp -n /workspace/claude/builder-project/.claude/memory/*.md \
  ~/.claude/projects/-workspace-claude-builder-project/memory/
```

- **First start (empty named volume)**: copies all committed memory files
- **Restart (existing named volume)**: `-n` flag preserves in-session writes

## What Claude Code Reads at Startup

When Claude starts with cwd=`/workspace/claude/builder-project`:
- `CLAUDE.md` (from cwd and parents)
- `.claude/settings.json` / `.claude/settings.local.json`
- `.claude/rules/*.md`
- `.claude/commands/`
- `.claude/skills/`
- `.claude/agents/`
- `.mcp.json`
- Memory from `~/.claude/projects/-workspace-claude-builder-project/memory/`

## Outbound Sync (sync-prj-repos-memory skill)

```bash
cp ~/.claude/projects/-workspace-claude-builder-project/memory/*.md \
  /workspace/claude/builder-project/.claude/memory/
git add .claude/memory/
git commit -m "sync: update memory from session"
git push
```

## Directory Path Canonicalization

`/workspace/claude/builder-project` → `-workspace-claude-builder-project`
Target: `~/.claude/projects/-workspace-claude-builder-project/`

## Relationship to Multi-Project Support

`load-projects.sh` accepts multiple repos:
```bash
load-projects.sh -live sun2admin/builder-project sun2admin/other-repo
```
- `-live` repo: cloned to `/workspace/claude/<name>`, memory seeded, path written to `~/live-project`
- Additional repos: cloned to `/workspace/repos/<name>`, no memory seeding
