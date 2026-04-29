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

## One Live Project Per Container

This skill operates on exactly one project — the live project. The one-container = one-live-session architecture means there is never more than one project to sync. The live project path is recorded in `~/live-project` by `load-projects.sh` at container start.

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
| `/sync-prj-repos-memory` (no args) | Read `~/live-project`, sync that project |
| `/sync-prj-repos-memory /workspace/claude/my-prj` | Sync the specified project path |

**No cwd detection.** cwd is unreliable at sync time — the Bash tool maintains a persistent shell, so `cd` commands during a session drift cwd away from the live project. `~/live-project` is always authoritative.

**`~/live-project` vs `/tmp/live-project`:** `~/live-project` is written to the claude user's home directory, which is more predictable and conventional than `/tmp`. `load-projects.sh` writes it fresh on every container start, so the file always reflects the current live project.

If `~/live-project` does not exist when the skill is invoked with no args, the skill exits with a clear error rather than guessing.

### Ownership Filtering

The skill only commits and pushes to repos owned by the authenticated GitHub user. You cannot push to repos you don't own — if a non-owned repo is somehow passed as an explicit path argument, it must be skipped entirely (no local memory sync, no commit, no push).

```bash
get_authenticated_user() {
  gh api user --jq '.login' 2>/dev/null || echo ""
}

get_repo_owner() {
  local project_path=$1
  local remote_url
  remote_url=$(git -C "$project_path" config --get remote.origin.url 2>/dev/null || echo "")
  [ -z "$remote_url" ] && return 1
  echo "$remote_url" | sed -E 's|.*[:/]([^/]+)/[^/]+/?$|\1|'
}
```

| Condition | Behavior |
|---|---|
| Remote owner matches auth user | Sync, commit, push |
| Remote owner differs from auth user | Skip entirely, log reason |
| No remote detectable | Treat as owned, sync and commit (no push) |
| `gh api user` fails | Log warning, proceed (cannot verify ownership) |

All skips are logged with the reason:
```
⊘ builder-project: skipping (owner: otherperson, authenticated: you)
```

### Project Discovery

No project discovery. The skill syncs exactly one project per invocation — either the live project from `~/live-project` or an explicit path argument. There is no "sync all" mode.

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
    # Bash fallback for images without rsync (current container stack)
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

  # Use git -C throughout — no cd, so cwd never changes
  git -C "$project_root" add -A

  if git -C "$project_root" diff --cached --quiet; then
    echo "  Nothing to sync"
    return 0
  fi

  local modified added deleted
  modified=$(git -C "$project_root" diff --cached --name-only --diff-filter=M | wc -l | tr -d ' ')
  added=$(git -C "$project_root" diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
  deleted=$(git -C "$project_root" diff --cached --name-only --diff-filter=D | wc -l | tr -d ' ')

  git -C "$project_root" commit -m "sync-prj-repos-memory: Sync memory and config (modified $modified, added $added, deleted $deleted)"

  local branch
  branch=$(git -C "$project_root" rev-parse --abbrev-ref HEAD)
  git -C "$project_root" push origin "$branch"
}
```

**Why `git add -A`:**
- Captures memory files just synced
- Captures skills/commands/agents/rules/settings.json Claude wrote to the repo during the session
- Captures deletions (skills/commands removed during session)
- `settings.local.json` is auto-gitignored, so it won't be staged even with `-A`

### main()

```bash
main() {
  if [[ $# -gt 0 ]]; then
    # Explicit path provided — use it directly
    sync_project "$1"
  else
    # No args — read live project from ~/live-project
    if [[ ! -f "$HOME/live-project" ]]; then
      echo "✗ ~/live-project not found — is load-projects.sh configured with -live?" >&2
      exit 1
    fi
    local live_path
    live_path=$(cat "$HOME/live-project")
    sync_project "$live_path"
  fi
}
```

## Error Handling

| Failure | Behavior |
|---|---|
| `~/live-project` missing (no args) | Hard error — exit 1 with clear message |
| Project is not a git repository | Skip with warning, exit non-zero |
| Ownership mismatch | Skip entirely (no memory sync, no commit, no push), log reason |
| No live memory directory | Skip memory sync, still commit any repo changes |
| git commit error | Log error, exit non-zero |
| git push error | Log error with details, exit non-zero |
| Nothing to sync | Report "Nothing to sync" — not an error |

## What Is and Is NOT Committed

| File | Committed? | Reason |
|---|---|---|
| `memory/*.md` | Yes | Core purpose of the skill |
| `skills/**`, `commands/**`, `agents/**`, `rules/**` | Yes (if modified) | Claude writes here during session — `git add -A` picks them up |
| `settings.json` | Yes (if modified) | Team-shared, in repo |
| `CLAUDE.md`, `.mcp.json` | Yes (if modified) | Team-shared, in repo |
| `settings.local.json` | **No** | Auto-gitignored (machine-local) |
| Session transcripts (`.jsonl`) | **No** | In named volume only, never in repo |

## Integration with Persistence Lifecycle

| Event | Script/Skill | What happens |
|---|---|---|
| Container rebuild | `load-projects.sh` | Clones live repo, seeds `memory/*.md` from git → named volume with `cp -n`, writes `~/live-project` |
| Container restart | `load-projects.sh` | `cp -n` skips existing files → in-session writes preserved, rewrites `~/live-project` |
| End of session | `/sync-prj-repos-memory` | Reads `~/live-project`, rsyncs memory from named volume → repo, commits all changes |
| Between sessions | git | Memory and all config portable, shared with team |

The two scripts are complementary — `load-projects.sh` is read-only (seeds from git), `/sync-prj-repos-memory` is write-only (commits back to git). Neither overwrites the other's work.

## Verification Tests

### Test 1: Skill discovery
```bash
/help | grep sync-prj-repos-memory
# Expect: skill appears with description
```

### Test 2: Sync live project (no args)
```bash
# Ensure ~/live-project exists and points to builder-project
cat ~/live-project
# Expect: /workspace/claude/builder-project

/sync-prj-repos-memory
# Expect:
# - memory/*.md in repo updated to match ~/.claude/projects/-workspace-claude-builder-project/memory/
# - Any new skills/commands in repo also committed
# - git log shows commit: "sync-prj-repos-memory: Sync memory and config (...)"
# - Push succeeded
```

### Test 3: Explicit project path
```bash
/sync-prj-repos-memory /workspace/claude/builder-project
# Expect: builder-project synced using provided path
```

### Test 4: Missing ~/live-project
```bash
mv ~/live-project ~/live-project.bak
/sync-prj-repos-memory
# Expect: clear error "~/live-project not found", exit non-zero
mv ~/live-project.bak ~/live-project
```

### Test 5: Stale memory file removal
```bash
touch /workspace/claude/builder-project/.claude/memory/stale-test.md
git -C /workspace/claude/builder-project add .claude/memory/stale-test.md
git -C /workspace/claude/builder-project commit -m "test: add stale file"
/sync-prj-repos-memory
# Expect: stale-test.md removed from repo
```

### Test 6: Nothing to sync
```bash
# Run sync twice in a row with no session changes between
/sync-prj-repos-memory
# Expect: "Nothing to sync" reported — no empty commit created
```

### Test 7: settings.local.json not committed
```bash
/sync-prj-repos-memory /workspace/claude/builder-project
git -C /workspace/claude/builder-project show HEAD --name-only | grep settings.local
# Expect: no output — settings.local.json never appears in commits
```

### Test 8: Ownership filtering
```bash
# Invoke with a path whose GitHub remote owner differs from gh whoami
/sync-prj-repos-memory /workspace/repos/someone-elses-repo
# Expect: ⊘ skip message with owner and auth user shown, no commit or push
```

## Implementation Phases

### Phase 1: Implement skill in builder-project repo ✅ COMPLETE
Committed to `sun2admin/builder-project` — `bb69e47`

### Phase 2: Verify load-projects.sh ✅ COMPLETE
1. ✅ Seeds only `memory/*.md` with `cp -n`
2. ✅ `cp -n` preserves in-session writes on restart
3. ✅ `canonicalize_path()` leading dash preserved — matches Claude Code
4. ✅ `-live` flag, single project seeding, `~/live-project` written
5. ✅ Non-live repos cloned to `/workspace/repos/`
Committed to `sun2admin/build-with-claude-stage2` — `26b8100`

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

### Phase 5: Clean up ✅ COMPLETE
Deleted `/workspace/claude/builder-project/.claude/commands/update-build-with-claude.md`
Committed to `sun2admin/builder-project` — `dced57a`

### Phase 6: Update skill implementation
1. Remove cwd detection from `main()`
2. Add `~/live-project` read for no-args invocation
3. Add ownership filtering via `gh api user --jq '.login'` + remote URL parsing
4. Remove "sync all projects" loop
5. Update `SKILL.md` invocation table
6. Update error handling for missing `~/live-project`
7. Commit and push to builder-project

### Phase 7: End-to-end verification
1. Run all 8 verification tests above
2. Confirm `~/live-project` is read correctly
3. Confirm ownership filtering skips non-owned repos
