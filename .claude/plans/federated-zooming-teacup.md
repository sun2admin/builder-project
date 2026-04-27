# init-projects.sh - Multi-Project Memory Seeding Script

## Context

Currently, `/workspace/.devcontainer/scripts/init-memory.sh` only seeds memory for a single hardcoded project (`-workspace`). This is insufficient because:

1. **Only one project seeded**: Supports only `/workspace/claude` → `~/.claude/projects/-workspace/`
2. **Incomplete seeding**: Copies only memory files, not the full `.claude/` configuration structure
3. **Projects can't be discovered**: No mechanism to find/seed multiple projects at `/workspace/claude/project-X/`
4. **Knowledge lost on rebuild**: Without complete configuration seeding, projects lose their full configuration when containers rebuild

**The solution**: Create `init-projects.sh` that:
- Discovers all valid projects in `/workspace/claude/`
- Seeds complete `.claude/` structure (not just memory)
- Handles multiple projects with correct canonical paths
- Preserves in-session memory changes via `cp -n`
- Provides clear status feedback on success/failure

## Implementation Plan

### 1. Overview and Functions

**Script location**: `/workspace/.devcontainer/scripts/init-projects.sh`

**Functions to implement**:
1. `canonicalize_path()` — Convert file path to canonical form for project ID
2. `discover_projects()` — Find all valid project directories under `/workspace/claude/` (those with `.claude/`)
3. `validate_project()` — Check if directory has `.claude/` subdirectory
4. `seed_project_config()` — Copy `.claude/` structure and root files to `~/.claude/projects/<path>/`
5. `seed_project_memory()` — Copy memory files with `cp -n` (no-overwrite) to preserve runtime changes
6. `main()` — Orchestrate discovery, validation, and seeding of all projects

**Reuse existing code**:
- `canonicalize_path()` logic exists in `/workspace/claude/.claude/scripts/init-workspace.sh` (lines 69-73)
- Bash patterns from `/workspace/.devcontainer/scripts/init-ssh.sh`, `init-gh-token.sh`
- Status tracking with checkmarks/X from init-workspace.sh

### 2. Canonical Path Calculation

**Algorithm** (from existing init-workspace.sh):
```bash
canonicalize_path() {
 local path=$1
 # Convert: /workspace/claude/project-a → -workspace-claude-project-a
 echo "$path" | sed 's|^/||;s|/|-|g'
}
```

**Examples**:
- `/workspace/claude/build-with-claude` → `-workspace-claude-build-with-claude`
- `/workspace/claude/project-a` → `-workspace-claude-project-a`
- `/workspace/claude/my-first-claude-prj` → `-workspace-claude-my-first-claude-prj`

### 3. Project Discovery

**Search location**: `/workspace/claude/`

**Valid projects**:
- Any subdirectory under `/workspace/claude/` that contains a `.claude/` directory
- The `.claude/` directory is the primary marker of a valid Claude project
- Example: `/workspace/claude/build-with-claude/`, `/workspace/claude/my-first-claude-prj/`

**Why `.claude/` validation**:
- Claude Code's discovery logic specifically looks for `.claude/` as the key indicator
- It encodes all project configuration (settings, memory, skills, rules, commands, agents)
- Presence/absence of `.claude/` is definitive: with it = project, without = not a project
- Files like `CLAUDE.md` and `.mcp.json` are optional, but `.claude/` is the standard marker

**Discovery logic**:
```
For each subdirectory in /workspace/claude/:
 If [ -d "<subdir>/.claude" ]:
 Add to projects_found array
```

### 4. Configuration Copying Specification

For each discovered project `/workspace/claude/<project-name>/`:

**Step 1: Calculate paths**
- Source base: `/workspace/claude/<project-name>`
- Target base: `~/.claude/projects/<canonical-path>`
- Example: `/workspace/claude/build-with-claude` → `~/.claude/projects/-workspace-claude-build-with-claude`

**Step 2: Copy `.claude/` structure** (use `cp -r`)
```
/workspace/claude/<project-name>/.claude/
├── settings.json → ~/.claude/projects/-workspace-claude-<project>/. claude/settings.json
├── settings.local.json → ~/.claude/projects/-workspace-claude-<project>/. claude/settings.local.json
├── rules/ → ~/.claude/projects/-workspace-claude-<project>/. claude/rules/ (entire tree)
├── commands/ → ~/.claude/projects/-workspace-claude-<project>/. claude/commands/ (entire tree)
├── skills/ → ~/.claude/projects/-workspace-claude-<project>/. claude/skills/ (entire tree)
├── agents/ → ~/.claude/projects/-workspace-claude-<project>/. claude/agents/ (entire tree)
└── memory/ → seed separately in Step 4
```

**Step 3: Copy root project files** (direct `cp`)
```
/workspace/claude/<project-name>/CLAUDE.md → ~/.claude/projects/-workspace-claude-<project>/CLAUDE.md
/workspace/claude/<project-name>/.mcp.json → ~/.claude/projects/-workspace-claude-<project>/.mcp.json (if exists)
```

**Step 4: Create memory directory and seed** (use `cp -n`)
```
Create: ~/.claude/projects/-workspace-claude-<project>/memory/ (if doesn't exist)
Copy: /workspace/claude/<project-name>/.claude/memory/*.md → ~/.claude/projects/-workspace-claude-<project>/memory/
Flag: cp -n (no-overwrite)

Why cp -n:
- On container restart (same devcontainerId): named volume persists, preserves in-session changes
- On container rebuild (new devcontainerId): named volume is fresh, cp -n has no effect (destination empty)
- Design: session modifications to memory persist across restarts (until rebuild wipes volume)
- Users must commit memory changes to git if they want to preserve beyond rebuild
```

### 5. Error Handling and Status Tracking

**Error strategy** (from existing scripts):
- `set -e` at top to exit on any error
- But allow specific failures (e.g., missing .mcp.json)
- Track successes and failures with counters
- Report summary at end

**Status tracking**:
- `projects_seeded=0` (successful seeds)
- `projects_failed=0` (failed seeds)
- Print `✓` for success, `✗` for failure on each project
- Final message: "Seeded N projects (M failed)"

**Expected errors to handle gracefully**:
- No projects found (valid, just continue)
- Project missing `.claude/` (skip with warning)
- Memory directory doesn't exist in source (skip with warning)
- `.mcp.json` missing (skip, it's optional)

### 6. Bash Script Structure

Follow patterns from existing init scripts:

```bash
#!/bin/bash
set -e

# Configuration constants
WORKSPACE_ROOT="/workspace/claude"
PROJECTS_BASE="$HOME/.claude/projects"

# Status tracking
projects_seeded=0
projects_failed=0

# Functions (in order):
canonicalize_path() { ... }
validate_project() { ... }
seed_project_config() { ... }
seed_project_memory() { ... }
discover_projects() { ... }
main() { ... }

# Call main
main
```

**Key conventions**:
- Use `local` for function variables
- Use arrays for project lists
- Use `mkdir -p` for safety
- Use clear variable names (not shortcuts)
- Use comments for non-obvious logic
- Use `2>/dev/null` to suppress expected "file not found" messages

Define 11 distinct states with clear entry/exit behavior:

```
INIT → Initialize; read --dry-run flag; transition to BASE_IMAGE
BASE_IMAGE → Display menu, wait for selection 1-6 / b(ack) / q(uit)
AI_SELECTION → Display menu, wait for selection 1-2 / b / q
PLUGIN_FETCH → Fetch available plugins from GitHub (non-interactive)
PLUGIN_SELECTION → Display menu, wait for selection 1-N / d(etails) / b / q
PROJECT_SEARCH → Search GitHub for projects with tag (non-interactive, unless --dry-run)
PROJECT_SELECTION → Display menu, wait for selection 1-N / n(one) / b / q
CLONE_INITIALIZE → Clone repo, run init-workspace.sh, validate (non-interactive)
SUMMARY_CONFIRM → Show summary of selections, confirm proceed / b / q
EXECUTE → Execute final steps: create sync skill, start Claude
DONE → Exit with success message

Back transitions:
- BASE_IMAGE + back → Quit (first layer)
- AI_SELECTION + back → BASE_IMAGE
- PLUGIN_SELECTION + back → AI_SELECTION
- PROJECT_SELECTION + back → PLUGIN_SELECTION
- CLONE_INITIALIZE + back → PROJECT_SELECTION
- SUMMARY_CONFIRM + back → PROJECT_SELECTION
- EXECUTE + back → SUMMARY_CONFIRM
```

### 7. Detailed Algorithm

**main() function flow**:

1. **Discover phase**:
 - Find all subdirectories in `/workspace/claude/`
 - For each subdirectory:
 - Check if `.claude/` subdirectory exists
 - If yes: add to projects array (skip validation - existence of .claude/ is proof of validity)
 - If no projects found: exit gracefully with message

2. **Seed phase** (for each discovered project):
 - Get project name (directory basename)
 - Calculate canonical path: `/workspace/claude/<project>` → `-workspace-claude-<project>`
 - Create target `~/.claude/projects/<canonical-path>/` directory
 - Copy entire `.claude/` structure with `cp -r` (preserves all subdirectories)
 - Copy `CLAUDE.md` (if exists, optional)
 - Copy `.mcp.json` (if exists, optional)
 - Create `memory/` directory in target
 - Copy memory files with `cp -n` (no-overwrite flag preserves runtime changes on restart)
 - Track success or failure for this project

3. **Report phase**:
 - Print summary: "Seeded X projects, Y failed"
 - Exit with code 0 (init scripts should not fail container startup)

**Pseudo-code**:

```
function main():
 projects=()
 
 # Discover phase: find all subdirs with .claude/
 for each subdir in /workspace/claude/:
 if [ -d "$subdir/.claude" ]:
 add subdir to projects array
 
 if projects is empty:
 echo "No Claude projects found in /workspace/claude/"
 return 0
 
 # Seed phase: copy config + memory for each project
 for each project_path in projects:
 try:
 project_name = basename(project_path)
 canonical_path = canonicalize_path(project_path)
 target = ~/.claude/projects/<canonical_path>
 
 mkdir -p $target
 cp -r $project_path/.claude/ $target/.claude/
 cp $project_path/CLAUDE.md $target/ (if exists)
 cp $project_path/.mcp.json $target/ (if exists)
 mkdir -p $target/memory/
 cp -n $project_path/.claude/memory/*.md $target/memory/ (if exists)
 
 projects_seeded++
 echo "✓ Seeded $project_name"
 catch error:
 projects_failed++
 echo "✗ Failed $project_name: $error"
 
 # Report phase
 echo "Seeded $projects_seeded projects"
 if [ $projects_failed -gt 0 ]:
 echo " (Failed: $projects_failed)"
 
 return 0 # Always succeed - don't fail container startup
```

### 8. Integration with devcontainer

**Current postStartCommand**:
```bash
sudo /usr/local/bin/init-firewall.sh && 
 /workspace/.devcontainer/scripts/init-ssh.sh && 
 /workspace/.devcontainer/scripts/init-gh-token.sh && 
 /workspace/.devcontainer/scripts/init-github-mcp.sh && 
 /workspace/.devcontainer/scripts/init-memory.sh
```

**After init-projects.sh**:
```bash
sudo /usr/local/bin/init-firewall.sh && 
 /workspace/.devcontainer/scripts/init-ssh.sh && 
 /workspace/.devcontainer/scripts/init-gh-token.sh && 
 /workspace/.devcontainer/scripts/init-github-mcp.sh && 
 /workspace/.devcontainer/scripts/init-projects.sh
```

**Notes**:
- Replace init-memory.sh (which only did single-project memory)
- init-projects.sh will handle memory seeding for all projects
- Called after networking + auth setup, before Claude starts
- Should not fail (return 0 even if no projects found)

### 9. Files to Create/Modify

**Files to CREATE**:
1. `/workspace/.devcontainer/scripts/init-projects.sh` (new multi-project script)

**Files to MODIFY**:
1. `/workspace/.devcontainer/devcontainer.json` (replace init-memory.sh with init-projects.sh in postStartCommand)

**Files to DELETE/ARCHIVE**:
1. `/workspace/.devcontainer/scripts/init-memory.sh` (no longer needed - replaced by init-projects.sh)

**Files NOT CHANGED**:
- `/workspace/claude/.claude/scripts/init-workspace.sh` (reuse logic, don't modify)
- `.devcontainer/scripts/init-ssh.sh`, `init-gh-token.sh`, `init-github-mcp.sh` (unchanged)

### 10. Verification and Testing Strategy

**Test 1: Single Project (build-with-claude)**
- Workspace at `/workspace/claude/build-with-claude/` with `.claude/` structure
- Start container
- Verify memory seeded to `~/.claude/projects/-workspace-claude-build-with-claude/memory/`
- Check count: 37+ files seeded
- Verify `.claude/` structure exists: settings.json, rules/, commands/, skills/, agents/
- Verify CLAUDE.md and .mcp.json copied

**Test 2: Multiple Projects**
- Create second test project: `/workspace/claude/test-project-a/` with `.claude/` structure
- Start container
- Verify both projects seeded:
 - `~/.claude/projects/-workspace-claude-build-with-claude/`
 - `~/.claude/projects/-workspace-claude-test-project-a/`
- Check both have complete config + memory

**Test 3: Memory Preservation on Restart (cp -n behavior)**
- Start container, verify memory seeded (37+ files in build-with-claude)
- Manually modify a memory file in running container (add a line to one .md file)
- Restart container (don't rebuild, same devcontainerId) — init-projects.sh runs again
- Verify modified line still present in memory file (cp -n preserved it, didn't overwrite)
- Verify unmodified memory files are still there (all 37+ files intact)

**Test 4: Memory Restoration on Rebuild**
- Modify a memory file in container
- Rebuild container (fresh devcontainerId, fresh named volume)
- Verify memory restored from git to `/workspace/claude/<project>/.claude/memory/`
- Verify restored to `~/.claude/projects/-workspace-claude-.../memory/` (37 files)
- Verify modified file not there (expected - new volume)

**Test 5: Edge Cases**
- Project with missing `.claude/`: should be skipped (not discovered)
- Project with missing `.claude/memory/`: should create memory dir, copy nothing, exit gracefully
- Project with missing `.mcp.json`: should seed without it (optional file)
- Path with special characters: should canonicalize correctly (spaces → dashes)
- Empty projects array: should exit with message "No Claude projects found"

**Test 6: Integration Test**
- Start container with init-projects.sh in postStartCommand
- Projects seeded successfully before Claude starts
- Run Claude session from `/workspace/claude/build-with-claude/`
- Memory accessible in Claude (can check `/help` for loaded skills)
- Switch cwd to different project and verify memory different

### 11. Critical Implementation Notes

1. **Do not hardcode project paths**: Use discovery loops
2. **Use canonical path logic consistently**: Don't replicate, reuse logic
3. **Handle missing optional files gracefully**: .mcp.json is optional, memory may be empty
4. **Use `cp -n` only for memory**: Other copies should be normal `cp` or `cp -r`
5. **Preserve exit codes properly**: Return 0 even if some projects fail (init scripts shouldn't crash startup)
6. **Follow bash conventions**: `set -e`, local variables, meaningful names
7. **Test with both interactive and automated starts**: Verify output is clear
8. **Document the script**: Comments for non-obvious logic