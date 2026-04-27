# Create /sync-prj-repos-memory Skill (Global Workspace Skill)

## Context

Currently there's a manual skill at `/update-build-with-claude` that syncs memory from live session back to a single project's git repo. This needs to be generalized into a workspace-level skill `/sync-prj-repos-memory` that can sync memory for ANY project.

**Architecture decision**: 
- Create new repo `claude-global-config` to hold workspace-level skills, MCP servers, and config
- Integrate into **ai-install-layer (Layer 2)** — the foundational layer all containers build on
- Skills in `~/.claude/skills/` will be available to all projects automatically
- This keeps global workspace tooling separate from project-specific code

## Current Implementation

The existing `/update-build-with-claude` command does:

1. **Sync memory files** (copy from live back to repo):
 - Source: `~/.claude/projects/workspace-claude/memory/*.md`
 - Dest: `/workspace/claude/.claude/memory/`
 - Mode: Complete sync (overwrite all, not incremental)

2. **Remove stale files**:
 - Any file in repo that's not in live memory gets deleted

3. **Verify counts match**:
 - File count check: live memory file count == repo memory file count

4. **Commit and push**:
 - `git add .claude/memory/ MEMORY.md`
 - Exclude sensitive files: `settings.local.json`
 - Create descriptive commit message
 - Push to origin main

**Problem**: This only works for the hardcoded `workspace-claude` project. The new skill needs to handle ALL projects.

## Design Decisions (Finalized)

1. **Repository**: New repo `claude-global-config`
 - Holds workspace-level skills, MCP servers, utilities, and config
 - Will be integrated into ai-install-layer (Layer 2)
 - Structure:
 ```
 claude-global-config/
 └── .claude/
 └── skills/
 └── sync-prj-repos-memory/
 ├── SKILL.md
 └── sync-prj-repos-memory.sh
 ```

2. **Skill name**: `/sync-prj-repos-memory` (generic, workspace-scoped)
 - Replaces hardcoded `/update-build-with-claude`
 - Works for any project in the workspace
 - Available globally from Layer 2

3. **Integration point**: ai-install-layer (Layer 2)
 - After `npm install -g @anthropic-ai/claude-code`
 - Clone `claude-global-config` repo
 - Copy skills to `~/.claude/skills/`
 - All downstream layers inherit the skills

4. **Execution context**: Automatic (required)
 - Runs automatically before container exit/rebuild
 - Ensures session changes are always persisted to git
 - Explicit manual invocation also possible: `/sync-prj-repos-memory`

5. **Scope**: All projects + ALL configuration
 - Discover all projects in ~/.claude/projects/
 - Sync EVERYTHING from `~/.claude/projects/<path>/.claude/` back to repo:
 - `memory/*.md` (auto-memory files)
 - `skills/` (newly created/modified skills)
 - `commands/` (newly created/modified commands)
 - `rules/` (newly created/modified rules)
 - `agents/` (newly created/modified agents)
 - `settings.json` (project settings)
 - `settings.local.json` (user-specific overrides, committed to git)
 - `.mcp.json` (MCP server config)
 - Use rsync with `--delete` to capture deletions
 - Deletions only persist if synced to git (ephemeral otherwise)

6. **Implementation**: Executable skill (shell script)
 - Full script implementation in sync-prj-repos-memory.sh
 - Self-contained, no supporting scripts needed
 - Uses rsync for robust directory sync with selective exclusions

## Implementation Approach: sync-prj-repos-memory Skill

### New skill location and structure:
```
claude-global-config/ (NEW REPO)
└── .claude/
 └── skills/
 └── sync-prj-repos-memory/
 ├── SKILL.md ← metadata and usage documentation
 └── sync-prj-repos-memory.sh ← bash implementation
```

### SKILL.md Structure
- **Name**: sync-prj-repos-memory
- **Description**: Sync memory from live session back to project git repositories
- **Usage**: `/sync-prj-repos-memory [project-path]`
- **Behavior**: 
 - If `project-path` provided: sync only that project
 - If no path provided and in a project dir: sync that project only
 - If no path and outside a project: sync all discovered projects
- **Output**: List of synced projects, file counts, git status

### sync-prj-repos-memory.sh Implementation

**What it needs to do** (generalized from current /update-build-with-claude):

For each project to sync:
1. **Find project root** — traverse up directory tree until .git/ found
2. **Calculate canonical path** — use canonicalize_path() from init-workspace.sh
3. **Check for outstanding uncommitted changes**:
 - Run `git status` in project directory
 - If uncommitted changes exist:
 - Commit them with auto-message: `sync-prj-repos-memory: [auto] Commit outstanding changes (modified X, added Y, deleted Z)`
4. **Sync entire .claude/ directory** from live to repo:
 - Source: `~/.claude/projects/<canonical-path>/.claude/`
 - Destination: `<project>/.claude/`
 - Method: rsync with --delete (captures new files, modifications, AND deletions)
 - Exclusions: none (sync everything including settings.local.json)
5. **Verify and commit**:
 - Stage: `git add .claude/ CLAUDE.md .mcp.json` (all .claude config + root files)
 - Commit with message: `sync-prj-repos-memory: Sync config and memory (modified X, added Y, deleted Z)`
 - Push to origin (detect branch)
6. **Report**:
 - Per-project status with ✓/✗
 - Files synced/deleted count
 - Git status (pushed, remote)
 - "nothing to sync" if no changes
 - Error messages on failure

**Key architectural points**:
- ✅ Syncs EVERYTHING (memory + all config files)
- ✅ Uses rsync with --delete to capture deletions
- ✅ Commit messages include skill name and [auto] for automated pre-sync commits
- ✅ Handles outstanding changes before syncing
- ✅ Works with init-projects.sh wipe-and-reseed pattern:
 - User deletes skill during session (from ~/.claude/projects/)
 - Sync skill syncs deletion to git with --delete
 - init-projects.sh wipes ~/.claude/projects/ on restart
 - init-projects.sh re-seeds from git (deletion persisted)

**Reusable code to leverage:**
- `canonicalize_path()` from `/workspace/claude/.claude/scripts/init-workspace.sh`
- `find_git_root()` pattern: traverse up to .git/
- Git workflow patterns: stage, commit, push
- Status reporting: checkmarks from build-workspace.sh

## Repos and Files to Create

### 1. Create new repo: claude-global-config
**GitHub repo**: `https://github.com/sun2admin/claude-global-config`

**Initial structure**:
```
claude-global-config/
├── README.md
└── .claude/
 └── skills/
 └── sync-prj-repos-memory/
 ├── SKILL.md
 └── sync-prj-repos-memory.sh
```

### 2. Files to create in claude-global-config
- `claude-global-config/.claude/skills/sync-prj-repos-memory/SKILL.md` — skill metadata, description, usage
- `claude-global-config/.claude/skills/sync-prj-repos-memory/sync-prj-repos-memory.sh` — executable bash script (chmod +x)

### 3. Modify ai-install-layer Dockerfile
**File**: `ai-install-layer/Dockerfile`

**Add after Claude Code install** (after `npm install -g @anthropic-ai/claude-code`):
```dockerfile
# Add global workspace skills from claude-global-config
RUN git clone https://github.com/sun2admin/claude-global-config /tmp/global-config && \
 mkdir -p /home/claude/.claude/skills && \
 cp -r /tmp/global-config/.claude/skills/* /home/claude/.claude/skills/ && \
 chown -R claude:claude /home/claude/.claude/skills && \
 rm -rf /tmp/global-config
```

### 4. Modify init-projects.sh
**File**: `/workspace/.devcontainer/scripts/init-projects.sh`

**Changes**:
- Update `seed_project_config()` to copy EVERYTHING including `settings.local.json`:
 ```bash
 # Copy entire .claude/ directory (including settings.local.json)
 if [ -d "$project_path/.claude" ]; then
 cp -r "$project_path/.claude" "$target_base/"
 fi
 ```
- **BEFORE seeding projects**, wipe the named volume: 
 ```bash
 # Wipe old session state, will be re-seeded from git
 rm -rf "$HOME/.claude/projects/"
 mkdir -p "$HOME/.claude/projects/"
 ```

### 5. Archive/delete in build-with-claude
- `/workspace/claude/.claude/commands/update-build-with-claude.md` — delete (replaced by /sync-prj-repos-memory in Layer 2)

**REUSE (don't modify):**
- `/workspace/claude/.claude/scripts/init-workspace.sh` — extract and reuse canonicalize_path() logic

## Verification and Testing

### Test 1: Skill discovery at startup
```
Start new container
/help | grep sync-prj-repos-memory
# Verify: skill appears in help output with description
```

### Test 2: Sync single project (cwd-based)
```
cd /workspace/claude
/sync-prj-repos-memory
# Verify:
# - Memory files copied from ~/.claude/projects/workspace-claude/memory/ to /workspace/claude/.claude/memory/
# - File counts match (ls -1 | wc -l comparison)
# - No stale files left behind
# - Git commit created with descriptive message
# - Push succeeded to origin main
```

### Test 3: Sync with explicit project path
```
cd /tmp
/sync-prj-repos-memory /workspace/claude/my-first-claude-prj
# Verify: only my-first-claude-prj synced, not build-with-claude
# - Memory from ~/.claude/projects/workspace-claude-my-first-claude-prj/ synced to project
# - Git commit and push succeeded in that project only
```

### Test 4: Sync all projects (no args, called outside project)
```
cd /tmp
/sync-prj-repos-memory
# Verify: discovers and syncs all projects
# - workspace-claude (build-with-claude)
# - workspace-claude-my-first-claude-prj
# - (any others)
# Each shows ✓ or ✗ status
```

### Test 5: Edge cases
- Missing live memory directory (should skip gracefully)
- No changes to sync (should report "nothing to sync")
- Git errors (missing .git, no remote, etc.) — report clearly
- Sensitive files not committed (settings.local.json, *.local.json)
- Stale file removal works (add/delete files in live, verify sync removes them from repo)

### Test 6: Integration
- Skill invocable as `/sync-prj-repos-memory` from Claude CLI
- Works in both interactive and piped input modes
- Can be called from cron/automation (no interactive prompts needed)

## Implementation Steps

### Phase 1: Create claude-global-config repo
1. Create new GitHub repo `sun2admin/claude-global-config`
2. Create `.claude/skills/sync-prj-repos-memory/` directory structure
3. Write SKILL.md with metadata, description, usage, and examples
4. Implement sync-prj-repos-memory.sh:
 - Argument parsing (optional project path)
 - Project discovery logic (find all in ~/.claude/projects/)
 - Project scope determination (arg vs cwd vs all)
 - canonicalize_path() function (copied from init-workspace.sh)
 - Outstanding changes auto-commit (check git status, commit if needed)
 - rsync for full .claude/ sync with --delete (captures all changes and deletions)
 - Git workflow (add, commit, push per project)
 - Status reporting with ✓/✗ indicators and "nothing to sync"
5. Make script executable: `chmod +x sync-prj-repos-memory.sh`
6. Commit and push to origin

### Phase 2: Update init-projects.sh
1. File: `/workspace/.devcontainer/scripts/init-projects.sh`
2. Add wipe step at start of `main()`: `rm -rf "$HOME/.claude/projects/"` (fresh start each container)
3. Verify `seed_project_config()` copies ENTIRE `.claude/` including `settings.local.json` (use `cp -r`)
4. Update `seed_project_memory()` to use `cp -r` instead of `cp -n`:
 - Reason: Sync skill runs automatically before exit, so git always has latest state
 - Fresh named volume on restart (wiped), no pre-existing files to conflict with
 - Regular overwrite is safe and simpler
5. Test: Run init-projects.sh, verify clean seed from git
6. Commit and push to build-with-claude

### Phase 3: Integrate into ai-install-layer (Layer 2)
1. Access `ai-install-layer` repo (https://github.com/sun2admin/ai-install-layer)
2. Update Dockerfile to clone and copy skills from claude-global-config
3. Add after `npm install -g @anthropic-ai/claude-code`:
 ```dockerfile
 RUN git clone https://github.com/sun2admin/claude-global-config /tmp/global-config && \
 mkdir -p /home/claude/.claude/skills && \
 cp -r /tmp/global-config/.claude/skills/* /home/claude/.claude/skills/ && \
 chown -R claude:claude /home/claude/.claude/skills && \
 rm -rf /tmp/global-config
 ```
4. Test build of ai-install-layer with :claude and :gemini variants
5. Push changes to ai-install-layer

### Phase 4: Set up automatic execution
1. Determine mechanism for automatic sync before container exit (hook, postAttachCommand, or other)
2. Ensure sync-prj-repos-memory runs automatically (transparent to user)
3. Document: "Sync runs automatically before rebuild; no manual action required"

### Phase 5: Clean up build-with-claude
1. Delete `/workspace/claude/.claude/commands/update-build-with-claude.md` (replaced by global skill)
2. Commit and push to build-with-claude repo

### Phase 6: Verify
1. Rebuild container with updated ai-install-layer and init-projects.sh
2. Verify `/sync-prj-repos-memory` appears in `/help`
3. Test all verification scenarios below

---

## What the Skill Currently Does (Summary)

**Current /update-build-with-claude implementation**:
1. Syncs memory from `~/.claude/projects/workspace-claude/memory/` → `/workspace/claude/.claude/memory/`
2. Removes stale files (in repo but not in live)
3. Verifies file counts match
4. Commits with message: lists modified, added, deleted files
5. Pushes to origin main

**What /sync-prj-repos-memory needs to do** (generalized):
1. Same memory sync logic, but for ALL projects (not hardcoded)
2. Discover projects in `~/.claude/projects/`
3. For each project:
 - Find git root
 - Calculate canonical path
 - Sync memory back to project repo
 - Remove stale files
 - Commit and push
4. Report per-project status

**Open questions for discussion**:
- Should it skip projects with no changes, or report "nothing to sync"?
- How should it handle failed syncs (one project fails, continue with others)?
- Should memory files be the only thing synced, or also `.claude/` config files?
- What should the commit message format be per project?
- Should it validate git is clean before syncing (no uncommitted changes)?