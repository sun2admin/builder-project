---
name: load-projects-retroactive-plan
description: Retroactive plan document for load-projects.sh implementation
---

# load-projects.sh - Remote Cloning and Local Project Seeding

## Context

The `/workspace/.devcontainer/scripts/load-projects.sh` script is responsible for discovering and seeding Claude projects on container startup. It supports two modes:

1. **Remote Cloning**: Clone specified projects from GitHub (e.g., `sun2admin/builder-project`) and seed their configuration
2. **Local Discovery**: Discover projects already present in `/workspace/claude/` and seed their configuration to `~/.claude/projects/`

Together, these modes ensure projects are discoverable across the container lifecycle and properly configured for multi-project workspace support.

## Problem Statement

Without project seeding on container startup:
- Cloned projects aren't available in Claude's `~/.claude/projects/` directory
- Local projects in `/workspace/claude/` aren't accessible to Claude
- Session memory and configuration are lost across container rebuilds
- Multi-project support is broken

## Solution

`load-projects.sh` combines remote cloning with local discovery to provide:
- Automatic cloning of specified GitHub repositories
- Automatic discovery and seeding of local projects
- Complete `.claude/` structure preservation (settings, memory, skills, commands, rules, agents)
- Canonical path generation for correct project identification
- Non-destructive memory seeding (preserves runtime changes with `cp -n`)
- Clear status feedback on seeding progress

## Implementation Details

### 1. Functions

**canonicalize_path()**
- Converts file paths to canonical form for project IDs
- Pattern: `/workspace/claude/project-name` → `-workspace-claude-project-name`
- Uses: `echo "$path" | sed 's|^/||;s|/|-|g'`

**clone_project()**
- Clones a remote GitHub repository
- Takes GitHub repo identifier (e.g., `sun2admin/builder-project`)
- Clones to `/workspace/claude/<project-name>`
- Validates clone completion

**discover_local_projects()**
- Searches `/workspace/claude/` for directories with `.claude/` subdirectory
- `.claude/` is the definitive marker of a valid Claude project
- Returns array of discovered project paths

**seed_project_config()**
- Copies `.claude/` directory structure from source to `~/.claude/projects/<canonical-path>/`
- Uses `cp -r` to preserve all subdirectories (settings, memory, skills, commands, rules, agents)
- Optionally copies `CLAUDE.md` and `.mcp.json` root files if present
- Returns 0 on success (optional files missing is not an error)

**seed_project_memory()**
- Copies memory files from source to target `memory/` directory
- Uses `cp -n` (no-overwrite) to preserve in-session changes on container restart
- Behavior:
  - On container restart (same devcontainerId): named volume persists, in-session changes preserved
  - On container rebuild (new devcontainerId): fresh volume, files seeded from source
- Returns 0 even if memory directory doesn't exist (expected on first run)

**main()**
- Orchestrates the full seeding workflow
- Execution order:
  1. Clone specified remote projects (if any)
  2. Discover local projects in `/workspace/claude/`
  3. Seed configuration and memory for all projects
  4. Report success/failure summary
  5. Exit with code 0 (init scripts must not fail container startup)

### 2. Canonical Path Algorithm

Converts file paths to canonical project identifiers for `~/.claude/projects/`:

```bash
canonicalize_path() {
  local path=$1
  # Remove leading slash, replace remaining slashes with dashes
  echo "$path" | sed 's|^/||;s|/|-|g'
}
```

**Examples**:
- `/workspace/claude/build-with-claude` → `-workspace-claude-build-with-claude`
- `/workspace/claude/my-first-claude-prj` → `-workspace-claude-my-first-claude-prj`
- `/workspace/my-workspace/project-a` → `-workspace-my-workspace-project-a`

### 3. Remote Project Cloning

**Input**: GitHub repository identifier (e.g., `sun2admin/builder-project`)

**Process**:
```bash
# Validate GitHub repo format
if [[ "$repo" != *"/"* ]]; then
  echo "Invalid repo format. Use: owner/repo"
  return 1
fi

# Extract project name from repo
project_name="${repo##*/}"

# Clone to /workspace/claude/<project-name>
clone_dir="/workspace/claude/$project_name"
git clone "https://github.com/$repo.git" "$clone_dir"

# Verify clone succeeded
if [[ ! -d "$clone_dir/.git" ]]; then
  return 1
fi
```

### 4. Local Project Discovery

**Search location**: `/workspace/claude/`

**Valid project criteria**:
- Directory exists under `/workspace/claude/`
- Contains `.claude/` subdirectory
- `.claude/` presence is definitive (no need to check for `CLAUDE.md` or `.mcp.json`)

**Discovery logic**:
```bash
discover_local_projects() {
  local projects=()
  for subdir in /workspace/claude/*/; do
    if [[ -d "$subdir.claude" ]]; then
      projects+=("$subdir")
    fi
  done
  echo "${projects[@]}"
}
```

### 5. Configuration Seeding

For each project (cloned or discovered):

**Step 1: Calculate paths**
```bash
source_dir="/workspace/claude/$(basename $project_path)"
canonical_id=$(canonicalize_path "$source_dir")
target_dir="$HOME/.claude/projects/$canonical_id"
```

**Step 2: Create target directory**
```bash
mkdir -p "$target_dir"
```

**Step 3: Copy `.claude/` structure**
```bash
cp -r "$source_dir/.claude/" "$target_dir/.claude/"
```

This preserves all subdirectories:
- `settings.json` — project settings
- `settings.local.json` — local user overrides
- `rules/` — project-specific rules
- `commands/` — project-level commands/skills
- `skills/` — project-level skills
- `agents/` — project-level agents
- `memory/` — project memory (seeded separately)

**Step 4: Copy optional root files**
```bash
[[ -f "$source_dir/CLAUDE.md" ]] && cp "$source_dir/CLAUDE.md" "$target_dir/"
[[ -f "$source_dir/.mcp.json" ]] && cp "$source_dir/.mcp.json" "$target_dir/"
```

**Step 5: Seed memory files**
```bash
mkdir -p "$target_dir/memory"
cp -n "$source_dir/.claude/memory"/*.md "$target_dir/memory/" 2>/dev/null || true
```

The `-n` flag means "no-overwrite": existing files in target are never overwritten. This preserves changes made during the container session.

### 6. Error Handling

**Strategy**:
- `set -e` at script top for fail-fast behavior
- Allow specific failures (missing optional files) to not break the script
- Track successes and failures with counters
- Return 0 on exit (init scripts must not fail container startup)

**Patterns**:
- Missing `.mcp.json`: Skip with warning, not an error
- Missing memory directory: Skip with warning, not an error
- Clone failure: Increment failure counter, continue with next project
- Configuration copy failure: Report with specific error, continue

### 7. Status Tracking

**Counters**:
- `clones_failed` — number of failed clones
- `projects_seeded` — number of successfully seeded projects
- `projects_failed` — number of failed seeds
- `projects_skipped` — number of skipped projects (wrong owner, etc.)

**Output**:
```
✓ Cloned sun2admin/builder-project
✓ Seeded build-with-claude
✓ Seeded my-first-claude-prj
✗ Failed to seed broken-project: missing .claude directory
Summary: Seeded 2 projects (1 failed, 1 skipped)
```

### 8. Integration with devcontainer.json

**postStartCommand** calls load-projects.sh in the init chain:

```bash
sudo /usr/local/bin/init-firewall.sh && \
  /workspace/.devcontainer/scripts/init-ssh.sh && \
  /workspace/.devcontainer/scripts/init-gh-token.sh && \
  /workspace/.devcontainer/scripts/init-github-mcp.sh && \
  /workspace/.devcontainer/scripts/load-projects.sh <remote-repos...>
```

**Execution order**:
1. Firewall (iptables egress rules)
2. SSH agent setup and key loading
3. GitHub PAT environment variable setup
4. GitHub MCP server binary installation
5. **Project cloning and seeding** ← load-projects.sh
6. Claude Code startup via postAttachCommand

**Why this order**:
- SSH and GitHub auth must be ready before cloning repos
- MCP server installed before Claude starts
- Projects must be seeded before Claude discovers them
- All init scripts complete before Claude Code starts

### 9. Behavior Under Different Conditions

**First Container Start (fresh devcontainerId)**:
- `clones_failed=0`: Clone specified repos successfully
- `projects_seeded=N`: Seed all discovered/cloned projects
- Memory directory created fresh and seeded from source
- Named volume for `~/.claude` is brand new

**Container Restart (same devcontainerId)**:
- Clones skipped (repos already exist in `/workspace/claude/`)
- Local projects discovered and seeded
- `cp -n` prevents overwriting in-session memory changes
- Named volume persists across restart

**Container Rebuild (new devcontainerId)**:
- Clones performed again (fresh workspace)
- Local projects discovered and seeded
- Memory restored from git-committed files
- New named volume with clean state

### 10. Files and Integration

**Files**:
- `/workspace/.devcontainer/scripts/load-projects.sh` — main script
- `/workspace/.devcontainer/devcontainer.json` — postStartCommand reference

**Related**:
- `/workspace/claude/.claude/scripts/init-workspace.sh` — reuses canonicalize_path pattern
- Git-committed project memory files enable seeding across rebuilds
- Named volume `claude-code-config-${devcontainerId}` stores live project state

### 11. Testing Scenarios

**Scenario 1: Remote cloning**
```bash
./load-projects.sh sun2admin/builder-project
```
Expected: Clones builder-project and seeds it

**Scenario 2: Local discovery only**
```bash
./load-projects.sh
```
Expected: Discovers projects in /workspace/claude/ and seeds them

**Scenario 3: Mixed (remote + local)**
```bash
./load-projects.sh sun2admin/builder-project
```
Expected: Clones builder-project AND discovers other local projects, seeds all

**Scenario 4: No projects**
```bash
./load-projects.sh  # (no local projects, no remote specified)
```
Expected: Exits gracefully with message, returns 0

**Scenario 5: Clone failure**
```bash
./load-projects.sh sun2admin/nonexistent-repo
```
Expected: Clone fails, projects_failed incremented, continue with local discovery, return 0

## Design Principles

1. **Non-destructive**: Uses `cp -n` for memory to preserve in-session changes
2. **Graceful failure**: Missing optional files (`.mcp.json`, memory dir) don't break seeding
3. **Clear feedback**: Status messages with `✓` and `✗` for each operation
4. **Always succeeds**: Returns 0 on exit even with failures (init scripts must not break container startup)
5. **Idempotent**: Can be called multiple times without issues (skips existing repos, respects in-session changes)
6. **Comprehensive**: Seeds entire `.claude/` structure, not just memory

## Summary

`load-projects.sh` is a comprehensive project seeding script that:
- Clones remote projects from GitHub into the container
- Discovers local projects already in `/workspace/claude/`
- Seeds complete project configuration to `~/.claude/projects/`
- Preserves in-session memory changes across restarts
- Enables multi-project workspace support
- Integrates seamlessly into the devcontainer startup sequence
