---
name: load-projects-retroactive-plan
description: Retroactive plan document for load-projects.sh — live project cloning, memory seeding, and persistence lifecycle
---

# load-projects.sh — Live Project Cloning and Memory Seeding

## Context

`/workspace/.devcontainer/scripts/load-projects.sh` runs on every container startup via `postStartCommand`. It has three responsibilities:

1. **Clone the live project** — Clone the `-live` repo to `/workspace/claude/<name>/` and seed its memory
2. **Clone side repos** — Clone any non-live repos to `/workspace/repos/<name>/` (no seeding)
3. **Write `~/live-project`** — Record the live project path so `postAttachCommand` knows where to `cd`

## One Container = One Live Session

This devcontainer runs a single Claude session. `postAttachCommand` starts Claude in the live project directory and that session runs for the lifetime of the container. There is no mechanism to switch between unrelated projects within a running Claude session — `/resume` for unrelated projects only copies a clipboard command, it does not auto-switch.

This means:
- Only the **live project** ever has a Claude session — only it needs memory seeded
- **Side repos** are working directories Claude edits from within the live session — their Claude config is never loaded, no seeding needed
- Seeding all discovered projects (old behavior) was wasteful — those directories were never read

## The -live Flag

```
load-projects.sh [-live owner/repo] [owner/repo ...]
```

| Argument | Clone target | Memory seeded | ~/live-project |
|---|---|---|---|
| `-live owner/repo` | `/workspace/claude/<name>` | Yes | Written with live path |
| `owner/repo` | `/workspace/repos/<name>` | No | — |
| *(none)* | Nothing cloned | No | Written with `$HOME` |

**Rules:**
- Only one `-live` is allowed — specifying more than one is a hard error
- Live repo clone failure is **fatal** — exits non-zero, container startup aborted
- Non-live repo clone failure is a **warning** — logged, script continues
- If no `-live` is specified, `~/live-project` is written with `$HOME` so `postAttachCommand` starts Claude from the home directory

## Why Memory Seeding Is Needed

Claude Code stores auto-memory outside the project repo:

> *"Auto memory is machine-local. All worktrees and subdirectories within the same git repository share one auto memory directory. Files are not shared across machines or cloud environments."* — Anthropic docs

Auto-memory path: `~/.claude/projects/<canonical-path>/memory/`

This lives in the **named Docker volume** (`~/.claude/`), which:
- Persists across container **restarts** (same `devcontainerId`)
- Is fresh/empty on container **rebuild** (new `devcontainerId`)

Without seeding, every rebuild loses all accumulated project memory. `load-projects.sh` bridges this gap by seeding memory from the git-committed repo copy into the named volume on startup.

## What Needs Seeding (and What Doesn't)

| File type | Seeded? | Why |
|---|---|---|
| `memory/*.md` | **Yes (live only)** | Written to named volume during session; must be re-seeded from git on rebuild |
| `skills/`, `commands/`, `agents/`, `rules/` | No | Written directly to repo (bind mount) — read from there via cwd walk-up |
| `settings.json` | No | Read directly from project repo via cwd walk-up |
| `CLAUDE.md`, `.mcp.json` | No | Read directly from project repo via cwd walk-up |
| `settings.local.json` | No | Machine-local, auto-gitignored — never seeded or committed |
| Session transcripts (`.jsonl`) | No | Session state only, machine-local, never committed |

**Key insight:** Claude reads all project config (skills, commands, settings, CLAUDE.md) directly from the bind-mounted project repo by walking up the directory tree from cwd. It does NOT read from `~/.claude/projects/<path>/.claude/`.

## The Full Persistence Lifecycle

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start  (live project only)
~/.claude/projects/<canonical-path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
~/.claude/projects/<canonical-path>/memory/  (updated in named volume)
    ↑  /sync-prj-repos-memory skill: rsync --delete + git commit + push
git repo (.claude/memory/*.md)  (committed, portable)
```

On **restart** (same devcontainerId):
- Named volume persists with in-session memory writes
- `cp -n` skips all existing files → preserves in-session writes

On **rebuild** (new devcontainerId):
- Named volume is brand new (empty)
- `cp -n` seeds all files from git → full memory restored

## Implementation Details

### 1. canonicalize_path()

Converts absolute project paths to the identifier format Claude Code uses for `~/.claude/projects/`:

```bash
canonicalize_path() {
  # Strip trailing slash, then replace / with -
  # Leading dash is intentional — Claude Code replaces all / with - without stripping the leading /
  echo "${1%/}" | sed 's|/|-|g'
}
```

**Examples:**
- `/workspace/claude/builder-project` → `-workspace-claude-builder-project`
- `/workspace/claude/builder-project/` → `-workspace-claude-builder-project` (trailing slash safe)

**Critical:** The leading dash is correct and must be preserved. Claude Code's actual canonical path for `/workspace/claude/builder-project` is `-workspace-claude-builder-project`. Scripts that strip the leading `/` (producing `workspace-...`) will seed to a directory Claude Code never reads.

This can be verified: session `.jsonl` files are written to `~/.claude/projects/-workspace-claude-builder-project/`, confirming the leading dash is Claude Code's actual format.

### 2. clone_repo()

Clones a GitHub repository to the specified target. Skips if the target already exists (restart case).

```bash
clone_repo() {
  local repo=$1 target=$2

  if [ -d "$target" ]; then
    echo "⊘ $(basename "$target"): already exists, skipping"
    return 0
  fi

  mkdir -p "$(dirname "$target")"
  git clone "https://github.com/$repo.git" "$target"
}
```

**Why HTTPS works without explicit credential setup:**

VS Code Dev Containers automatically injects a git credential helper into every container at startup:
```
credential.helper = !f() { node /tmp/vscode-remote-containers-*.js git-credential-helper $*; }; f
```
This helper proxies git auth requests back to the **host machine's credential store** (macOS keychain, Windows Credential Manager, etc.). The container never handles credentials directly — the host's existing GitHub auth is forwarded transparently.

This is a VS Code implicit behavior, not set up by any init script:
- ✓ HTTPS cloning works out of the box inside VS Code Dev Containers
- ✗ Not portable — CI/CD pipelines, `docker run`, or GitHub Codespaces won't have this helper

SSH remains available via `init-ssh.sh` for push and other git operations.

### 3. seed_memory()

Seeds `memory/*.md` from the git-committed repo into the named volume. Only called for the live project.

```bash
seed_memory() {
  local project_path=$1
  local canonical_id target_memory
  canonical_id=$(canonicalize_path "$project_path")
  target_memory="$HOME/.claude/projects/$canonical_id/memory"

  mkdir -p "$target_memory"

  if [ -d "$project_path/.claude/memory" ]; then
    cp -n "$project_path/.claude/memory"/*.md "$target_memory/" 2>/dev/null || true
  fi
}
```

**Why `cp -n`:**
- Never overwrites → in-session memory writes survive container restart
- `rsync --delete` would destroy session writes on restart
- `cp` without `-n` would overwrite on restart

### 4. main()

```bash
main() {
  parse_args "$@"

  # Live project: clone to /workspace/claude/, seed memory, write ~/live-project
  if [ -n "$live_repo" ]; then
    local live_name live_path
    live_name=$(echo "$live_repo" | cut -d'/' -f2)
    live_path="$LIVE_WORKSPACE/$live_name"

    clone_repo "$live_repo" "$live_path" || {
      echo "✗ Failed to clone live repo $live_repo — aborting" >&2
      exit 1
    }

    seed_memory "$live_path"
    echo "$live_path" > ~/live-project
  else
    echo "$HOME" > ~/live-project
  fi

  # Non-live repos: clone to /workspace/repos/, no seeding
  if [ ${#other_repos[@]} -gt 0 ]; then
    mkdir -p "$REPOS_WORKSPACE"
    for repo in "${other_repos[@]}"; do
      clone_repo "$repo" "$REPOS_WORKSPACE/$(echo "$repo" | cut -d'/' -f2)" \
        || echo "⚠ Failed to clone $repo (non-fatal)"
    done
  fi
}
```

## ~/live-project Contract

`load-projects.sh` writes the live project's absolute path to `~/live-project` (`/home/claude/live-project`). `postAttachCommand` reads it to determine where to `cd` before starting Claude. The sync skill reads it to find the live project when invoked with no arguments.

```bash
# In devcontainer.json postAttachCommand:
bash --login -c 'cd $(cat ~/live-project 2>/dev/null || echo ~) && claude --dangerously-skip-permissions'
```

- If `-live` was specified → file contains `/workspace/claude/<live-name>`
- If no `-live` → file contains `$HOME`
- If file is missing (abnormal) → falls back to `~`

`~/live-project` is written to the claude user's home directory — more predictable and conventional than `/tmp`. `load-projects.sh` writes it fresh on every container start (restart and rebuild), so the file always reflects the current live project. Persistence across rebuilds is not needed since the file is always rewritten before anything reads it.

## Error Handling

| Failure | Behavior |
|---|---|
| Multiple `-live` flags | Hard error — exit 1 with message |
| `-live` with no following argument | Hard error — exit 1 with message |
| Live repo clone failure | Hard error — exit 1, container startup aborted |
| Non-live repo clone failure | Warning logged, script continues |
| Missing memory directory | `2>/dev/null \|\| true` — graceful, no files seeded |
| `cp -n` partial failure | Non-fatal — some files may not seed, project still accessible |

**Design choice:** Live repo clone failure is fatal because without the live project, there is nothing meaningful for Claude to do in the container. Non-live repo failures are non-fatal because they are side repos — the session can proceed without them.

## Integration with devcontainer.json

```json
"postStartCommand": "sudo /usr/local/bin/init-firewall.sh && \
  /workspace/.devcontainer/scripts/init-ssh.sh && \
  /workspace/.devcontainer/scripts/init-gh-token.sh && \
  /workspace/.devcontainer/scripts/init-github-mcp.sh && \
  /workspace/.devcontainer/scripts/load-projects.sh -live sun2admin/builder-project",

"postAttachCommand": "bash --login -c 'cd $(cat ~/live-project 2>/dev/null || echo ~) && claude --dangerously-skip-permissions'"
```

**Why this order matters:**
1. Firewall first — iptables rules established before any network calls
2. SSH + gh-token before cloning — git auth must be ready before `clone_repo()`
3. GitHub MCP binary before Claude — MCP server must exist before Claude starts
4. `load-projects.sh` last — live project must be cloned and seeded before Claude starts

## Behavior Under Different Conditions

| Condition | Live repo | Non-live repos | Memory seeding | Result |
|---|---|---|---|---|
| First start (fresh devcontainerId) | Cloned | Cloned | Seeds all `memory/*.md` | Full memory restored from git |
| Restart (same devcontainerId) | Skipped (exists) | Skipped (exists) | `cp -n` skips existing files | In-session writes preserved |
| Rebuild (new devcontainerId) | Cloned fresh | Cloned fresh | Seeds all `memory/*.md` | Full memory restored from git |
| No `-live` specified | N/A | Cloned if listed | No seeding | Claude starts from `$HOME` |

## Session Switching and /resume

`/resume` lists session `.jsonl` files from `~/.claude/projects/`. Switching to an unrelated project copies a `cd + claude --resume <id>` command to the clipboard — it does not auto-switch within the running session. Memory seeding creates `memory/*.md` files but does NOT create `.jsonl` session files; those only exist after Claude has been started in that project at least once.

**Implication:** `load-projects.sh` cannot make a side repo appear in `/resume`. Side repos are working directories only — Claude edits them from within the live session without ever switching project context.

## Design Principles

1. **One live project per container** — One container = one Claude session = one live project. Side repos are editing targets, not sessions.
2. **Explicit over discovered** — The `-live` flag makes intent explicit. No project discovery, no ownership filtering.
3. **Memory-only seeding** — Only `memory/*.md` belongs in `~/.claude/projects/`. All other config is read from the repo via cwd walk-up.
4. **Non-destructive** — `cp -n` never overwrites. In-session writes always survive restarts.
5. **Fail fast on live, warn on side** — Live repo clone failure aborts startup. Non-live failures are warnings.
6. **Idempotent** — Safe to call multiple times. Already-cloned repos are skipped. `cp -n` skips already-seeded files.

## Files

- `/workspace/.devcontainer/scripts/load-projects.sh` — this script
- `/workspace/.devcontainer/devcontainer.json` — `postStartCommand` and `postAttachCommand`
- `~/live-project` — live project path written by this script, read by `postAttachCommand`
- `<live-project>/.claude/memory/*.md` — source of truth for seeded memory
- `~/.claude/projects/<canonical-path>/memory/` — seeding target (named volume)
- `/workspace/claude/<live-name>/` — live project clone location
- `/workspace/repos/<name>/` — non-live repo clone location
