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

4. **Execution context**: Manual or automatic
 - Explicit invocation: `/sync-prj-repos-memory`
 - Automatic before container exit is ideal but not required to preserve skills/commands (those write to repo directly)
 - Auto-memory in named volume is the only thing at risk if not synced before rebuild
 - ⚠️ REVISED: Wipe-and-reseed (`rm -rf ~/.claude/projects/`) is NOT needed or recommended — `cp -n` on load correctly handles the restart vs rebuild distinction

5. **Scope**: All projects + correct sync targets
 - Discover all projects in ~/.claude/projects/
 - ⚠️ REVISED: Do NOT rsync `~/.claude/projects/<path>/.claude/` back to repo — that copy is stale seeded data
 - Claude writes skills, commands, agents, rules, settings.json directly to the repo (bind mount) during sessions — they are already in the right place
 - Only two sync operations needed:
   1. Copy `~/.claude/projects/<path>/memory/*.md` → `<repo>/.claude/memory/` (memory is the only thing written outside the repo)
   2. `git add -A && git commit && git push` (captures memory + any new skills/commands/etc Claude wrote to repo)
 - `settings.local.json` lives in repo `.claude/` (auto-gitignored) — do not commit it
 - Deletions of skills/commands: handled naturally since Claude deletes from repo directly; git status shows them

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
4. **Sync memory back to repo**:
 - Source: `~/.claude/projects/<canonical-path>/memory/*.md`
 - Destination: `<project>/.claude/memory/`
 - Method: `cp` (memory is the only thing written outside the repo)
 - Note: Skills/commands/agents/rules/settings.json are already in the repo (Claude writes there directly)
5. **Verify and commit**:
 - Stage: `git add -A` (captures memory updates + any new/modified/deleted skills, commands, etc.)
 - Commit with message: `sync-prj-repos-memory: Sync memory and config (modified X, added Y, deleted Z)`
 - Push to origin (detect branch)
6. **Report**:
 - Per-project status with ✓/✗
 - Files synced count
 - Git status (pushed, remote)
 - "nothing to sync" if no changes
 - Error messages on failure

**Key architectural points**:
- ✅ Syncs memory (the only thing written outside repo) + commits all repo changes
- ✅ `git add -A` naturally captures deletions (skills/commands deleted from repo during session)
- ✅ Commit messages include skill name and [auto] for automated pre-sync commits
- ✅ Handles outstanding changes before syncing
- ✅ Do NOT sync `~/.claude/projects/<path>/.claude/` back to repo — that is a stale seed artifact

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

### 4. Verify load-projects.sh
**File**: `/workspace/.devcontainer/scripts/load-projects.sh`

**Correct behavior** (no changes needed if already implemented correctly):
- Seeds only `memory/*.md` into `~/.claude/projects/<canonical-path>/memory/`
- Uses `cp -n` (no-overwrite) to preserve in-session writes on container restart
- Does NOT copy entire `.claude/` tree — Claude reads config from repo directly
- Does NOT wipe `~/.claude/projects/` — `cp -n` correctly handles restart vs rebuild

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
 - Copy memory: `cp ~/.claude/projects/<path>/memory/*.md <repo>/.claude/memory/`
 - `git add -A && git commit && git push` (captures memory + all repo changes)
 - Status reporting with ✓/✗ indicators and "nothing to sync"
5. Make script executable: `chmod +x sync-prj-repos-memory.sh`
6. Commit and push to origin

### Phase 2: Verify load-projects.sh
1. File: `/workspace/.devcontainer/scripts/load-projects.sh`
2. Confirm: NO wipe of `~/.claude/projects/` (cp -n handles restart vs rebuild correctly)
3. Confirm: seeds only `memory/*.md` — NOT entire `.claude/` tree
4. Confirm: uses `cp -n` (no-overwrite) to preserve in-session memory writes on restart
5. Test: Run load-projects.sh, verify memory seeded correctly from git
6. Commit and push if any corrections needed

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
1. Rebuild container with updated ai-install-layer and load-projects.sh
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