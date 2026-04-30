# Plan: Rename plugins/ → layer3-ai-plugins/

## Goal
Rename the `plugins/` subdirectory in builder-project to `layer3-ai-plugins/` to
align with the layer naming convention established by layer1-ai-depends and
layer2-ai-install. Scope is the builder-project subdir only — the 8 individual
plugin GitHub repos and their images are not renamed.

---

## Files to Change

### Step 1: Rename the directory
- `plugins/` → `layer3-ai-plugins/`

### Step 2: Update layer3-ai-plugins/CLAUDE.md content
- Line 3: `ghcr.io/sun2admin/ai-install-layer:claude` → `ghcr.io/sun2admin/layer2-ai-install:claude`
- Line 47: `ai-install-layer` → `layer2-ai-install`

### Step 3: Update root CLAUDE.md
- Architecture table: `\`plugins/\`` → `\`layer3-ai-plugins/\``

### Step 4: Update .claude/plans/builder-project-restructure.md
- `plugins/CLAUDE.md` → `layer3-ai-plugins/CLAUDE.md`

### Step 5: Update .claude/settings.local.json
- 5 hardcoded Bash permission entries referencing `plugins/` → `layer3-ai-plugins/`

---

## Not Changing
- The 8 individual plugin GitHub repos and GHCR images — subdir rename only
- Memory files — existing `plugins/` references are all to `~/.claude/plugins/`
  (Claude Code's installed plugins dir), not the builder-project subdir

---

## Status
- [x] Step 1: Rename directory
- [x] Step 2: Update layer3-ai-plugins/CLAUDE.md
- [x] Step 3: Update root CLAUDE.md
- [x] Step 4: Update builder-project-restructure.md plan
- [x] Step 5: Update settings.local.json
- [x] Complete
