---
name: sync-prj-repos-memory-skill-plan
description: Design and implementation plan for the /sync-prj-repos-memory global workspace skill
---

# /sync-prj-repos-memory — Global Workspace Skill

## What It Does

`/sync-prj-repos-memory` is the **outbound half** of the memory persistence lifecycle:

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start       ← inbound
~/.claude/projects/<path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
~/.claude/projects/<path>/memory/  (updated in named volume)
    ↑  /sync-prj-repos-memory: rsync + git commit/push  ← outbound (this skill)
git repo (.claude/memory/*.md)  (committed, portable)
```

Without this skill, memory written during a session lives only in the named volume. It survives a container restart but is lost on rebuild. This skill commits it back to git so it survives rebuilds and is portable across machines.

## Why "sync-prj-repos-memory" and Not a Broader Sync

Claude writes skills, commands, agents, rules, and settings.json **directly to the project repo** (bind mount) during sessions — they are already in git. The only thing written *outside* the repo is auto-memory, which goes to the named volume at `~/.claude/projects/<path>/memory/`.

So the sync operations are:
1. **Memory**: `rsync --delete` from named volume → repo (handles new, modified, AND deleted files)
2. **Everything else**: `git add -A && git commit && git push` (picks up anything Claude wrote to the repo: new skills, deleted commands, modified settings, etc.)

## Skill Specification

### Location and Delivery

**Current (Phase 1):** Project-scoped skill in `builder-project` repo:

```
builder-project/
└── .claude/
    └── skills/
        └── sync-prj-repos-memory/
            ├── SKILL.md
            └── sync-prj-repos-memory.sh   (chmod +x)
```

Available immediately — Claude discovers it via cwd walk-up from `/workspace/claude/builder-project`. No image rebuild needed.

**Future (Phase 3):** Migrate to `claude-global-config`, baked into **ai-install-layer (Layer 2)**:

```
claude-global-config/
└── .claude/
    └── skills/
        └── sync-prj-repos-memory/
            ├── SKILL.md
            └── sync-prj-repos-memory.sh   (chmod +x)
```

```dockerfile
RUN git clone https://github.com/sun2admin/claude-global-config /tmp/global-config && \
    mkdir -p /home/claude/.claude/skills && \
    cp -r /tmp/global-config/.claude/skills/* /home/claude/.claude/skills/ && \
    chown -R claude:claude /home/claude/.claude/skills && \
    rm -rf /tmp/global-config
```

All containers built on Layer 2 will inherit the skill automatically after migration.

### Invocation

```
/sync-prj-repos-memory [project-path]
```

| Invocation | Behavior |
|---|---|
| `/sync-prj-repos-memory` (from inside a git repo) | Sync the current project only |
| `/sync-prj-repos-memory /workspace/claude/my-prj` | Sync the specified project only |
| `/sync-prj-repos-memory` (from outside any git repo) | Sync ALL projects in `/workspace/claude/` |

### Project Discovery

For "sync all" mode, projects are discovered from `/workspace/claude/` (not from `~/.claude/projects/`). This avoids the reverse-mapping problem: canonical IDs like `workspace-claude-my-prj` cannot be reliably reverse-mapped to paths because project names can contain hyphens that collide with the path separator.

```bash
for subdir in /workspace/claude/*/; do
  [[ -d "$subdir.claude" ]] && sync_project "$subdir"
done
```

For single-project mode, the git root is found by traversing up from cwd:
```bash
find_git_root() {
  local dir="${1:-$PWD}"
  while [[ "$dir" != "/" ]]; do
    [[ -d "$dir/.git" ]] && echo "$dir" && return 0
    dir=$(dirname "$dir")
  done
  return 1
}
```

## Core Sync Logic

### canonicalize_path()

Same algorithm as `load-projects.sh` — must produce identical output for the paths to match:

```bash
canonicalize_path() {
  echo "${1%/}" | sed 's|/|-|g'
}
# /workspace/claude/builder-project  → -workspace-claude-builder-project
# /workspace/claude/builder-project/ → -workspace-claude-builder-project (trailing slash safe)
# Leading dash is intentional — Claude Code replaces all / with - without stripping the leading /.
```

### Memory Sync (rsync --delete with bash fallback)

```bash
sync_memory() {
  local project_root=$1
  local canonical_id
  canonical_id=$(canonicalize_path "$project_root")
  local live_memory="$HOME/.claude/projects/$canonical_id/memory"
  local repo_memory="$project_root/.claude/memory"

  # Skip if named volume has no memory for this project
  [[ -d "$live_memory" ]] || { echo "  No live memory found, skipping"; return 0; }

  mkdir -p "$repo_memory"

  if command -v rsync &>/dev/null; then
    # rsync preferred: handles new, modified, and deleted files in one pass
    rsync -a --delete "$live_memory/" "$repo_memory/"
  else
    # Bash fallback for images without rsync (e.g. current container stack)
    # Step 1: copy new/modified files from live → repo
    cp -f "$live_memory"/*.md "$repo_memory/" 2>/dev/null || true
    # Step 2: remove files in repo not present in live (mirrors rsync --delete behavior)
    for f in "$repo_memory"/*.md; do
      [[ -f "$live_memory/$(basename "$f")" ]] || rm -f "$f"
    done
  fi
}
```

**Why not plain `cp`:**
- `cp` copies new and modified files but leaves stale files behind
- If Claude deleted a memory file during the session, `cp` would leave the old version in git
- Both `rsync --delete` and the bash fallback mirror the live state exactly, including deletions

**Why the dual approach:**
- `rsync` is cleaner and handles the sync atomically but is not installed in the current container stack
- The bash fallback produces identical results using only standard tools guaranteed to be present
- `command -v rsync` detects availability at runtime — if rsync is added to the image later, it is used automatically with no code changes needed

### Git Commit

```bash
commit_project() {
  local project_root=$1

  # Use git -C throughout — no cd, so no working directory state leaks between projects
  git -C "$project_root" add -A

  # Check if there's anything to commit
  if git -C "$project_root" diff --cached --quiet; then
    echo "  Nothing to sync"
    return 0
  fi

  # Build a descriptive commit message
  local modified added deleted
  modified=$(git -C "$project_root" diff --cached --name-only --diff-filter=M | wc -l | tr -d ' ')
  added=$(git -C "$project_root" diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
  deleted=$(git -C "$project_root" diff --cached --name-only --diff-filter=D | wc -l | tr -d ' ')

  git -C "$project_root" commit -m "sync-prj-repos-memory: Sync memory and config (modified $modified, added $added, deleted $deleted)"

  # Detect current branch and push
  local branch
  branch=$(git -C "$project_root" rev-parse --abbrev-ref HEAD)
  git -C "$project_root" push origin "$branch"
}
```

**Why `git add -A`:**
- Captures memory files just synced via rsync
- Captures skills/commands/agents/rules/settings.json Claude wrote to the repo during the session
- Captures deletions (skills/commands removed during session)
- `settings.local.json` is auto-gitignored, so it won't be staged even with `-A`

### Per-Project Sync Flow

```bash
sync_project() {
  local project_root=$1
  local name
  name=$(basename "$project_root")

  echo "Syncing $name..."

  # Step 1: Sync memory from named volume → repo
  sync_memory "$project_root" || { echo "✗ $name: memory sync failed"; return 1; }

  # Step 2: Stage + commit + push everything
  commit_project "$project_root" || { echo "✗ $name: git commit/push failed"; return 1; }

  echo "✓ $name"
}
```

## Error Handling

| Failure | Behavior |
|---|---|
| No live memory directory | Skip memory sync, still commit any repo changes |
| rsync error | Log error, skip this project, continue with others |
| git commit error | Log error, skip this project, continue with others |
| git push error (no remote, auth failure) | Log error with details, skip push only |
| Project has no `.git` | Skip entirely with warning |
| Nothing to sync | Report "Nothing to sync" — not an error |

**One project failing never stops others from syncing.**

## What Is and Is NOT Committed

| File | Committed? | Reason |
|---|---|---|
| `memory/*.md` | Yes | Core purpose of the skill |
| `skills/**`, `commands/**`, `agents/**`, `rules/**` | Yes (if modified) | Claude writes here during session — `git add -A` picks them up |
| `settings.json` | Yes (if modified) | Team-shared, in repo |
| `CLAUDE.md`, `.mcp.json` | Yes (if modified) | Team-shared, in repo |
| `settings.local.json` | **No** | Auto-gitignored (machine-local) |
| Session transcripts (`.jsonl`) | **No** | In named volume only, never in repo |
| `~/.claude/projects/<path>/.claude/` | **No** | Stale seed artifact, never synced back |

## Integration with Persistence Lifecycle

| Event | Script/Skill | What happens |
|---|---|---|
| Container rebuild | `load-projects.sh` | Clones repos, seeds `memory/*.md` from git → named volume with `cp -n` |
| Container restart | `load-projects.sh` | `cp -n` skips existing files → in-session writes preserved |
| End of session | `/sync-prj-repos-memory` | Rsyncs memory from named volume → repo, commits all changes |
| Between sessions | git | Memory and all config portable, shared with team |

The two scripts are complementary — `load-projects.sh` is read-only (seeds from git), `/sync-prj-repos-memory` is write-only (commits back to git). Neither overwrites the other's work.

## Verification Tests

### Test 1: Skill discovery
```bash
/help | grep sync-prj-repos-memory
# Expect: skill appears with description
```

### Test 2: Sync current project
```bash
cd /workspace/claude/builder-project
# Write a memory file in live session (or let Claude write one)
/sync-prj-repos-memory
# Expect:
# - memory/*.md in repo updated to match ~/.claude/projects/workspace-claude-builder-project/memory/
# - Any new skills/commands in repo also committed
# - git log shows commit: "sync-prj-repos-memory: Sync memory and config (...)"
# - Push succeeded
```

### Test 3: Explicit project path
```bash
cd /tmp
/sync-prj-repos-memory /workspace/claude/builder-project
# Expect: only builder-project synced, not any other projects
```

### Test 4: Sync all projects
```bash
cd /tmp  # outside any git repo
/sync-prj-repos-memory
# Expect: all projects in /workspace/claude/ discovered and synced
# Each shows ✓ or ✗
```

### Test 5: Stale memory file removal
```bash
# Add extra file to repo memory that doesn't exist in live
touch /workspace/claude/builder-project/.claude/memory/stale-test.md
git -C /workspace/claude/builder-project add .claude/memory/stale-test.md
git -C /workspace/claude/builder-project commit -m "test: add stale file"
# Now run sync
/sync-prj-repos-memory /workspace/claude/builder-project
# Expect: stale-test.md removed from repo (rsync --delete removes it)
```

### Test 6: Nothing to sync
```bash
# Run sync twice in a row with no session changes between
/sync-prj-repos-memory
# Expect: "Nothing to sync" reported — no empty commit created
```

### Test 7: settings.local.json not committed
```bash
ls /workspace/claude/builder-project/.claude/settings.local.json  # exists
/sync-prj-repos-memory /workspace/claude/builder-project
git -C /workspace/claude/builder-project show HEAD --name-only | grep settings.local
# Expect: no output — settings.local.json never appears in commits
```

## Implementation Phases

### Phase 1: Implement skill in builder-project repo
1. Create `.claude/skills/sync-prj-repos-memory/` in builder-project
2. Write `SKILL.md` — name, description, usage, behavior
3. Implement `sync-prj-repos-memory.sh` with:
   - `canonicalize_path()` — strip leading `/`, replace `/` with `-`
   - `find_git_root()` — traverse up to `.git/`
   - `discover_projects()` — find `.claude/` dirs under `/workspace/claude/`
   - `sync_memory()` — `rsync -a --delete` live → repo
   - `commit_project()` — `git add -A`, build message, commit, push
   - `sync_project()` — orchestrate per project
   - `main()` — parse args, determine scope, loop
5. `chmod +x sync-prj-repos-memory.sh`
6. Commit and push

### Phase 2: Verify load-projects.sh ✅ COMPLETE
1. ✅ Seeds only `memory/*.md` with `cp -n` — `seed_project_config()` removed
2. ✅ No wipe of `~/.claude/projects/`
3. ✅ `cp -n` preserves in-session writes on restart
4. ✅ `canonicalize_path()` trailing slash fix applied
Committed to `sun2admin/build-with-claude-stage2` — `be946de`

### Phase 3: Migrate to claude-global-config and ai-install-layer (Layer 2)
1. Create `claude-global-config` repo with `.claude/skills/sync-prj-repos-memory/` structure
2. Move skill files from builder-project into claude-global-config
3. Update `ai-install-layer/Dockerfile` — clone claude-global-config, copy skills to `~/.claude/skills/`
4. Build and test `:claude` and `:gemini` variants
5. Push — all downstream layers inherit the skill automatically

### Phase 4: Automatic execution (optional)
- Claude Code hooks (`PostToolUse` or session-end) could invoke the skill automatically
- Manual invocation is sufficient for now — the named volume protects against restart loss; only rebuild requires a manual sync before rebuild
- Document: "Run `/sync-prj-repos-memory` before rebuilding the container"

### Phase 5: Clean up
1. Delete `/workspace/claude/.claude/commands/update-build-with-claude.md` — replaced by this skill
2. Commit and push to builder-project

### Phase 6: End-to-end verification
1. Rebuild container
2. Verify skill appears in `/help`
3. Run all 7 verification tests above
