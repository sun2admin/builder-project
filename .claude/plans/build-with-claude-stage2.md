# build-with-claude-stage2: Test Container for Layer 4 Deployment Architecture

## Context

We are creating a test/staging environment (`build-with-claude-stage2`) to validate our future Layer 4 deployment pattern and the `/sync-prj-repos-memory` skill without risking the production `build-with-claude` repo.

**Why stage2 is needed:**
- Test the multi-project discovery mechanism (init-projects.sh finding projects under /workspace/claude/)
- Validate the canonical path calculation and memory seeding for /workspace/claude/<project>/ structure
- Prove the sync-prj-repos-memory skill works with this directory layout
- Validate complete end-to-end architecture: init-projects.sh → memory seeding → sync skill
- All without affecting production build-with-claude repo

**Key architectural insight:**
Future Layer 4 projects will have this structure:
- Project repo root has minimal devcontainer config
- On startup, clones actual project (e.g., builder-project) to /workspace/claude/<project>/
- init-projects.sh discovers and seeds all projects under /workspace/claude/
- sync-prj-repos-memory syncs from ~/.claude/projects/ back to git
- This pattern scales to multiple projects

## Implementation Plan

### Phase 1: Create build-with-claude-stage2 Repository

**Task 1.1: Create new GitHub repo**
- Create `sun2admin/build-with-claude-stage2` (private)
- Description: "Test container for Layer 4 deployment architecture and multi-project setup"
- Topic: `claude-prj` (marked as Claude project)
- Initialize with README.md

**Task 1.2: Set up minimal devcontainer structure**
- Copy `.devcontainer/devcontainer.json` from build-with-claude
- Copy all init scripts: init-ssh.sh, init-gh-token.sh, init-github-mcp.sh, init-projects.sh
- Copy init-firewall.sh to scripts/ if needed
- Update devcontainer.json:
 - Reference Layer 3 plugin image (same as build-with-claude): `ghcr.io/sun2admin/claude-plugins-a7f3d2e8:latest`
 - Keep postStartCommand with: firewall, ssh, gh-token, github-mcp, init-projects.sh
 - Add postAttachCommand: cd to /workspace/claude/builder-project before starting Claude

**Task 1.3: Add repository setup scripts**
- Create `.devcontainer/scripts/clone-builder-project.sh` (to be run at startup)
 - Clones builder-project to /workspace/claude/builder-project
 - Called as part of container initialization
 - Or: integrate into postStartCommand as part of init sequence

**Task 1.4: Push initial structure to stage2 repo**
- Commit: "Initial stage2 setup: minimal devcontainer structure"

### Phase 2: Merge and Sync All ~/.claude/projects/* Files to builder-project

**Files Found in ~/.claude/projects/:**
- `-workspace/memory/` — 37 memory files (legacy/older session)
- `workspace-claude/` — Current session structure with:
 - `.claude/settings.json`, `.claude/settings.local.json`, `.mcp.json`, `CLAUDE.md`
 - `memory/` — 37 memory files (same as `-workspace/memory/`)
- Session transcript files `.jsonl` (to be excluded - local debugging data)

**Task 2.1: Review and merge memory files**
- **Source 1**: `-workspace/memory/*.md` (37 files, dated April 20, 2025)
- **Source 2**: `workspace-claude/memory/*.md` (37 files, dated April 26, 2025)
- **Diff analysis performed**: MD5 checksums confirm ALL 37 files have IDENTICAL CONTENT
 - Differences are timestamp-only (not content differences)
 - `-workspace/` is legacy from older session
 - `workspace-claude/` is current session (more recent)
- **Merge decision**: Use `workspace-claude/memory/` as authoritative source
- **Action**: Copy all 37 memory files + MEMORY.md index from `workspace-claude/memory/` to builder-project `.claude/memory/`
- **Result**: 37 deduplicated, content-verified memory files synced to builder-project

**Task 2.2: Copy .claude/ subdirectories**
- `.claude/settings.json` — ✓ include (project settings)
- `.claude/settings.local.json` — ✓ include (user settings/overrides for stage2 inheritance)
- `.claude/commands/` — ✓ include all
- `.claude/skills/` — ✓ include all
- `.claude/agents/` — ✓ include all (if populated)
- `.claude/rules/` — ✓ include all (if populated)
- `.claude/scripts/` — ✓ include all (if populated)

**Task 2.3: Sync all plan files from /home/claude/.claude/plans/**
- Copy `/home/claude/.claude/plans/*.md` to builder-project `.claude/plans/`
- Include all active plans:
 - `update-build-with-claude.md` (sync-prj-repos-memory skill design)
 - `build-with-claude-stage2.md` (this plan)
 - `federated-zooming-teacup.md` (init-projects.sh plan)
 - Any other plans

**Task 2.4: Explicitly excluded from sync**
- All `.jsonl` files in `-workspace-claude/` (session transcripts - local debugging data, not needed for stage2)
- `-workspace/` directory itself (legacy project state, superseded by `workspace-claude/`)
- Any obsolete/deprecated files (none identified in content review)

**Task 2.5: Commit and push merged files to builder-project**
- Commit message: "Merge and sync all .claude/ config, memory, and plans from build-with-claude session"
- Detailed commit description listing what was merged/cleaned
- Verify all files present in builder-project repo on GitHub

**Task 2.6: Verify final builder-project structure**
- `.claude/memory/` — 37 merged memory files + MEMORY.md index
- `.claude/plans/` — all active plan files
- `.claude/settings.json` — project settings
- `.claude/commands/` — all project commands
- `.claude/skills/` — all project skills
- `.claude/agents/` — all project agents
- `.claude/rules/` — all project rules
- `.claude/scripts/` — all project scripts
- `.mcp.json` — MCP configuration
- `CLAUDE.md` — project documentation

### Phase 3: Test the Architecture

**Task 3.1: Start container with stage2 devcontainer**
- Container starts with build-with-claude-stage2 config
- postStartCommand runs:
 1. init-firewall.sh
 2. init-ssh.sh
 3. init-gh-token.sh
 4. init-github-mcp.sh
 5. Clone builder-project to /workspace/claude/builder-project
 6. init-projects.sh (discovers and seeds /workspace/claude/builder-project)

**Task 3.2: Verify init-projects.sh discovery**
- Check that `/workspace/claude/builder-project/` is discovered (has `.claude/` directory)
- Verify memory seeded to `~/.claude/projects/workspace-claude-builder-project/memory/`
- Check file count: all 37+ memory files present
- Verify settings.json, commands/, skills/, agents/ present in ~/.claude/projects/

**Task 3.3: Start Claude in builder-project**
- cd /workspace/claude/builder-project
- Execute: `claude --dangerously-skip-permissions`
- Verify Claude loads with all seeded memory and skills

**Task 3.4: Test manual memory modifications**
- Create a new memory file in ~/.claude/projects/workspace-claude-builder-project/memory/
- Verify it's accessible in Claude session
- Make modifications to existing memory files
- Verify changes persist in live session

### Phase 4: Prepare for sync-prj-repos-memory Testing

**Task 4.1: Verify sync-prj-repos-memory skill prerequisites**
- Plan file exists: `/home/claude/.claude/plans/update-build-with-claude.md` ✓
- Skill implementation ready (from future phase)
- Canonical path is correctly calculated: `workspace-claude-builder-project`

**Task 4.2: Document expected behavior**
- When sync-prj-repos-memory runs with stage2 as cwd:
 - Discovers /workspace/claude/builder-project as the project
 - Syncs from ~/.claude/projects/workspace-claude-builder-project/ to /workspace/claude/builder-project/.claude/
 - Commits with: `sync-prj-repos-memory: Sync config and memory (modified X, added Y, deleted Z)`
 - Pushes to builder-project repo origin
 - All memory and config updates persisted to git

### Files to Create/Modify

**New files in build-with-claude-stage2 repo:**
- `.devcontainer/devcontainer.json` (copy from build-with-claude)
- `.devcontainer/scripts/init-ssh.sh` (copy)
- `.devcontainer/scripts/init-gh-token.sh` (copy)
- `.devcontainer/scripts/init-github-mcp.sh` (copy)
- `.devcontainer/scripts/init-projects.sh` (copy)
- `.devcontainer/scripts/clone-builder-project.sh` (new - optional if integrated into postStartCommand)
- `README.md` (explain stage2 purpose and usage)

**Files to populate in builder-project repo:**
- `.claude/memory/` — sync all from ~/.claude/projects/workspace-claude/memory/
- `.claude/plans/` — copy from /home/claude/.claude/plans/
- These are already partially in builder-project (from previous task) but must include ALL memory and ALL plans

**Files NOT modified:**
- build-with-claude repo remains unchanged (production environment)

### Verification Checklist

**After stage2 creation:**
- [ ] build-with-claude-stage2 GitHub repo created and private
- [ ] Devcontainer.json properly configured
- [ ] All init scripts copied and functional
- [ ] README.md explains purpose and flow

**After memory/plans sync:**
- [ ] builder-project contains all 37+ memory files in .claude/memory/
- [ ] MEMORY.md index file present in builder-project
- [ ] All plan files in builder-project/.claude/plans/
- [ ] Commit and push successful to builder-project repo

**After container startup:**
- [ ] init-projects.sh discovers /workspace/claude/builder-project
- [ ] Memory seeded to ~/.claude/projects/workspace-claude-builder-project/memory/
- [ ] All 37+ files present in seeded memory
- [ ] Claude starts successfully in /workspace/claude/builder-project
- [ ] Memory and skills accessible in Claude session

**Before sync-prj-repos-memory testing:**
- [ ] This plan documented in builder-project
- [ ] update-build-with-claude.md (sync skill plan) in builder-project
- [ ] Canonical path correctly calculated
- [ ] All prerequisites met

## Notes

- **Minimal staged deployment**: stage2 only contains devcontainer config, not full build-with-claude files
- **Knowledge inheritance**: builder-project inherits all memory from build-with-claude session via memory sync
- **Plan documentation**: Architecture decisions documented in builder-project for future reference
- **Zero production risk**: All testing on stage2, build-with-claude untouched
- **Future proof**: This pattern will be the template for deploying Layer 4 projects