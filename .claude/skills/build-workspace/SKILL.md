---
name: build-workspace
description: Scaffold a new Claude or Gemini workspace with all dependencies configured
shortcut: bw
usage: |
  /build-workspace [--dry-run]
  
  Interactively scaffold a new workspace with base image, AI install-layer,
  plugin layer, and optional GitHub project repo.
  
  Options:
    --dry-run    Test the menu flow without executing commands or making changes
---

# /build-workspace

Build a new Claude or Gemini development workspace from scratch.

## Workflow Overview

1. **Select base image** — System packages and tools variant
2. **Select AI install-layer** — Claude or Gemini CLI
3. **Select plugins layer** — Pre-baked plugins (with option to view details)
4. **Discover projects** — Search GitHub for `<ai>-prj` tagged repos
5. **Validate and clone** — Verify GHCR image exists, clone repo if selected
6. **Initialize and start** — Seed memory, create sync skill, start Claude

## Step 0: Base Image Selection

Choose the base-ai-layer variant:

- **light** — Minimal (Python, git, curl)
- **latest** — Default (light + dev tools + graphics)
- **playwright_with_chromium** — latest + Playwright Chromium
- **playwright_with_firefox** — latest + Playwright Firefox
- **playwright_with_webkit** — latest + Playwright WebKit
- **playwright_with_all** — latest + all Playwright browsers

## Step 1: AI Install-Layer Selection

Choose the AI CLI to bake into the image:

- **claude** — Claude Code CLI + base plugins
- **gemini** — Gemini Code CLI + base plugins (future)

## Step 1a: Plugins Layer Selection

Dynamically discovers available plugin layers:

**For Claude:**
- Shows all repos matching `claude-plugins-*` with `anthropic-plugins` topic
- Displays name, description, and included plugins
- Option to view plugin details before selecting
- Example: `claude-plugins-a7f3d2e8` (build-repo-plugins)

**For Gemini:**
- Placeholder: "Gemini plugins coming soon"
- Uses empty plugin layer for now

## Step 2: GitHub Project Discovery

Searches for repositories tagged with `<ai>-prj`:

- `claude-prj` for Claude projects
- `gemini-prj` for Gemini projects (future)
- Displays repo name, description, last updated
- Allows selection or "None"

## Step 3: Validation and Cloning

For each candidate repo:

1. **Validate GHCR image** — Check if built image exists
2. **If image missing** — Ask user if they want to build it
3. **If yes** — Trigger build (or link to build instructions)
4. **If no** — Skip that option
5. **Clone repo** — Full clone to `/workspace/<ai>/<project>/`

## Step 4: Memory Initialization and Setup

If project selected:

1. **Run init-workspace.sh** (before setting cwd)
   - Discovers all `.claude/` dirs under `/workspace/<ai>/`
   - Validates `.git` exists in each project
   - Seeds memory to `~/.claude/projects/<canonical-path>/memory/`

2. **Create sync skill**
   - Creates `/workspace/<ai>/<project>/.claude/commands/sync-workspace-repo/SKILL.md`
   - Syncs memory back to git on demand
   - Auto-commits and pushes

3. **Start Claude**
   - Sets cwd to `/workspace/<ai>/<project>/`
   - Executes: `claude --dangerously-skip-permissions`

## Step 5: If No Project Selected

- Skip sync skill creation
- Set cwd to `/workspace`
- Execute: `claude --dangerously-skip-permissions`

## Key Features

### Dynamic Discovery
- Base images: Fetched from base-ai-layer repo tags
- AI install-layers: Fetched from ai-install-layer repo tags
- Plugin layers: Fetched from repos with `anthropic-plugins` topic
- Project repos: Searched via GitHub API with `<ai>-prj` tag

### Validation
- GHCR image existence verified before offering
- Project structure validated (requires `.claude/` directory)
- Git repository required (`.git` must exist)

### Memory Persistence
- Committed memory seeded from git on startup
- init-workspace.sh uses `cp -n` to preserve live changes
- sync-workspace-repo skill auto-commits updates back to git

### Configuration
- Base image determines system capabilities
- AI install-layer determines CLI and base plugins
- Plugin layer determines pre-baked plugins
- Project selection determines workspace content and context

## Error Handling

- Missing GHCR images: Offer to build or skip
- Clone failures: Full error message and exit
- Invalid project structure: Full error message and exit
- Missing .git: Full error message and exit

## Notes

- All discovery (images, install-layers, plugins, projects) happens dynamically per invocation
- Memory seeding works across restarts and container rebuilds
- Multiple projects can coexist under `/workspace/<ai>/` with separate memory namespaces
- Each project has separate sync skill for independent memory management
