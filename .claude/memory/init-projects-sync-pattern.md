---
name: load-projects and sync-prj-repos-memory — Correct Pattern
description: Definitive reference for what load-projects.sh must seed and what sync-prj-repos-memory must sync. Confirmed against official Anthropic docs and live container observation. Replaces earlier incorrect version that over-seeded .claude/ config directories.
type: project
---

## The Fundamental Insight

Claude Code reads project config (skills, commands, agents, rules, settings.json) **directly from the project repo** by walking up from cwd. It does NOT read from `~/.claude/projects/<path>/.claude/`. Therefore:

- **load-projects.sh only needs to seed `memory/`** — not the entire `.claude/` tree
- **sync-prj-repos-memory only needs to sync `memory/` back** — everything else is already in the repo

## What load-projects.sh Must Copy (and Why)

### ✓ MUST seed: memory files only
```bash
mkdir -p "$target_dir/memory"
cp -n "$source_dir/.claude/memory"/*.md "$target_dir/memory/" 2>/dev/null || true
```
**Why**: Auto-memory is written to `~/.claude/projects/<path>/memory/` by Claude Code internally. This directory is machine-local and lost on rebuild. Seeding from git-committed files restores it.

**Use `cp -n`**: Named volume persists across container restarts (same devcontainerId). `-n` preserves any in-session memory writes that occurred before restart.

### ✗ Do NOT seed: .claude/ config tree
**Why not**: Claude reads `.claude/skills/`, `.claude/commands/`, `.claude/agents/`, `.claude/rules/`, `.claude/settings.json` directly from the project repo (bind mount), not from `~/.claude/projects/<path>/.claude/`. Seeding these is wasted work and risks stale copies causing confusion.

### ✗ Do NOT seed: CLAUDE.md, .mcp.json
**Why not**: Claude reads these from the project repo (bind mount) directly. They do not need to exist in `~/.claude/projects/`.

## Correct load-projects.sh Seed Logic

```bash
seed_project() {
  local source_dir="$1"   # e.g. /workspace/claude/builder-project
  local canonical_id
  canonical_id=$(canonicalize_path "$source_dir")
  local target_dir="$HOME/.claude/projects/$canonical_id"

  mkdir -p "$target_dir/memory"

  # Only seed memory — everything else Claude reads from the repo directly
  if [ -d "$source_dir/.claude/memory" ]; then
    cp -n "$source_dir/.claude/memory"/*.md "$target_dir/memory/" 2>/dev/null || true
  fi
}
```

## What sync-prj-repos-memory Must Sync (and Why)

### ✓ MUST sync back: memory files
```bash
cp "$HOME/.claude/projects/$canonical_id/memory/"*.md \
   "$project_root/.claude/memory/" 2>/dev/null || true
git -C "$project_root" add .claude/memory/
```
**Why**: Auto-memory is written to the named volume. To persist across rebuilds and machines, it must be committed to the repo.

### ✓ MUST commit: any repo changes Claude made during the session
```bash
# Skills, commands, agents, rules, settings.json — Claude writes these to the repo directly
git -C "$project_root" add -A
git -C "$project_root" commit -m "sync-prj-repos-memory: Sync memory and config"
git -C "$project_root" push
```
**Why**: When Claude creates a new skill or modifies settings during a session, those writes go to the repo (bind mount). The sync skill just needs to commit them — they're already in the right place.

### ✗ Do NOT sync back: .claude/ from projects dir to repo
**Why not**: The `.claude/` copy in the projects dir is a stale seed artifact. Syncing it back would overwrite newer repo files with stale seeded versions.

## Canonical Path Algorithm

```bash
canonicalize_path() {
  local path=$1
  # Strip leading slash, replace remaining slashes with dashes
  echo "$path" | sed 's|^/||;s|/|-|g'
}

# Examples:
# /workspace/claude/builder-project → workspace-claude-builder-project
# /workspace/claude/my-first-prj   → workspace-claude-my-first-prj
```

**Note**: No leading dash. Derived from git repository root, not cwd. All subdirectories within the same git repo share one memory directory.

## Complete Flow Diagram

```
Container start:
  load-projects.sh
    git clone <repo> → /workspace/claude/<project>/      (if remote)
    cp -n .claude/memory/*.md → ~/.claude/projects/<path>/memory/   (seed memory only)

Session active:
  Claude reads config: /workspace/claude/<project>/.claude/  (from repo, via cwd walk-up)
  Claude writes skills/commands/settings: /workspace/claude/<project>/.claude/  (to repo)
  Claude writes memory: ~/.claude/projects/<path>/memory/   (to named volume)

Session end (sync-prj-repos-memory):
  cp memory/*.md → .claude/memory/       (bring memory into repo)
  git add -A && git commit && git push   (commit everything)
```

## Why cp -n Is Still Correct for Load

Even though we only seed memory (not the full `.claude/` tree), `cp -n` remains the right flag:
- Named volume persists across container **restarts** (same devcontainerId)
- Without `-n`: restart overwrites in-session memory Claude wrote before restart
- With `-n`: in-session memory survives restart, repo memory seeds only empty slots

## What About settings.local.json?

Claude Code writes `settings.local.json` to `.claude/settings.local.json` in the **project repo** and auto-gitignores it. Do not seed it into `~/.claude/projects/.claude/`. Do not sync it back. It is machine-local state; gitignored is correct.
