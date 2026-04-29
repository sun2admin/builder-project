---
name: load-projects-retroactive-plan
description: Retroactive plan document for load-projects.sh — project cloning, memory seeding, and persistence lifecycle
---

# load-projects.sh — Project Cloning and Memory Seeding

## Context

`/workspace/.devcontainer/scripts/load-projects.sh` runs on every container startup via `postStartCommand`. It has two responsibilities:

1. **Remote Cloning** — Clone specified GitHub projects (e.g., `sun2admin/builder-project`) into `/workspace/claude/`
2. **Memory Seeding** — Seed each project's `memory/*.md` from the git-committed repo into the named volume at `~/.claude/projects/<canonical-path>/memory/`

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
| `memory/*.md` | **Yes** | Written to named volume during session; must be re-seeded from git on rebuild |
| `skills/`, `commands/`, `agents/`, `rules/` | No | Written by Claude directly to the project repo (bind mount) — already there |
| `settings.json` | No | Read directly from project repo via cwd walk-up |
| `CLAUDE.md`, `.mcp.json` | No | Read directly from project repo via cwd walk-up |
| `settings.local.json` | No | Machine-local, auto-gitignored — must not be seeded or committed |
| Session transcripts (`.jsonl`) | No | Session state only, never committed |

**Key insight:** Claude reads all project config (skills, commands, settings, CLAUDE.md) directly from the bind-mounted project repo by walking up the directory tree from cwd. It does NOT read from `~/.claude/projects/<path>/.claude/`. The projects directory is session state only.

## The Full Persistence Lifecycle

```
git repo (.claude/memory/*.md)
    ↓  load-projects.sh: cp -n on container start
~/.claude/projects/<path>/memory/  (named volume)
    ↓  Claude writes auto-memory during session
~/.claude/projects/<path>/memory/  (updated in named volume)
    ↑  /sync-prj-repos-memory skill: rsync --delete + git commit + push
git repo (.claude/memory/*.md)  (committed, portable)
```

On **restart** (same devcontainerId):
- Named volume persists with in-session memory writes
- `cp -n` skips all existing files → preserves in-session writes

On **rebuild** (new devcontainerId):
- Named volume is brand new (empty)
- `cp -n` seeds all files from git → full memory restored

This means `cp -n` correctly handles both cases with no wipe-and-reseed needed.

## Implementation Details

### 1. canonicalize_path()

Converts absolute project paths to the identifier format Claude uses for `~/.claude/projects/`:

```bash
canonicalize_path() {
  local path=$1
  # Strip trailing slash (glob paths include it), then replace / with -
  # Leading dash is intentional — Claude Code does not strip the leading /
  echo "${path%/}" | sed 's|/|-|g'
}
```

**Examples:**
- `/workspace/claude/builder-project` → `-workspace-claude-builder-project`
- `/workspace/claude/builder-project/` → `-workspace-claude-builder-project` (trailing slash safe)
- `/workspace/claude/my-first-prj` → `-workspace-claude-my-first-prj`

**Important:** The leading dash is correct. Claude Code canonicalizes paths by replacing all `/` with `-` without stripping the leading slash. Scripts that strip the leading `/` produce `workspace-...` — that format is wrong and will seed to a directory Claude never reads.

### 2. clone_project()

Clones a GitHub repository into `/workspace/claude/` if it doesn't already exist:

```bash
clone_project() {
  local repo=$1  # format: owner/repo-name
  local project_name="${repo##*/}"
  local clone_dir="/workspace/claude/$project_name"

  # Skip if already cloned (restart case)
  [[ -d "$clone_dir/.git" ]] && return 0

  git clone "https://github.com/$repo.git" "$clone_dir"
  [[ -d "$clone_dir/.git" ]] || return 1
}
```

**Why HTTPS works without explicit credential setup:**

VS Code Dev Containers automatically injects a git credential helper into every container at startup:
```
credential.helper = !f() { node /tmp/vscode-remote-containers-*.js git-credential-helper $*; }; f
```
This helper proxies git auth requests back to the **host machine's credential store** (macOS keychain, Windows Credential Manager, etc.). The container never handles credentials directly — the host's existing GitHub auth is forwarded transparently.

This is a VS Code implicit behavior, not set up by any init script. It means:
- ✓ HTTPS cloning works out of the box inside VS Code Dev Containers
- ✗ Not portable — CI/CD pipelines, `docker run`, or GitHub Codespaces won't have this helper

For this stack (VS Code Dev Containers only), HTTPS is fine and simpler than SSH for cloning. SSH remains available via `init-ssh.sh` for operations that need it (push, other git operations).

### 3. Project Discovery (inlined in main)

Local project discovery is inlined directly into `main()` rather than extracted into a separate function. This avoids the subshell + word-split anti-pattern (`projects=($(discover_local_projects))`), which loses array structure and breaks on paths with spaces.

**Detection criterion:** presence of `.claude/` subdirectory — the definitive marker of a Claude project.

### 4. seed_project_memory()

Seeds `memory/*.md` from the git-committed repo into the named volume:

```bash
seed_project_memory() {
  local project_path=$1
  local canonical_id
  canonical_id=$(canonicalize_path "$project_path")
  local target_dir="$HOME/.claude/projects/$canonical_id/memory"

  mkdir -p "$target_dir"

  # cp -n: no-overwrite preserves in-session writes on restart
  # 2>/dev/null || true: graceful if source memory dir is empty or missing
  cp -n "$project_path/.claude/memory"/*.md "$target_dir/" 2>/dev/null || true
}
```

**Why `cp -n` and not `cp -r` or `rsync`:**
- `cp -n` never overwrites → in-session memory writes survive container restart
- `rsync --delete` would destroy session writes → wrong behavior on restart
- `cp -r` without `-n` would overwrite → wrong behavior on restart

### 5. main()

```bash
main() {
  # Clone any specified remote repos first
  for repo in "$@"; do
    clone_project "$repo" && echo "✓ Cloned $repo" || echo "✗ Failed to clone $repo"
  done

  # Discover and seed all local projects — inlined to avoid subshell/word-split issues
  for subdir in /workspace/claude/*/; do
    [[ -d "${subdir}.claude" ]] || continue
    local project="${subdir%/}"
    seed_project_memory "$project" \
      && echo "✓ Seeded $(basename "$project")" \
      || echo "✗ Failed to seed $(basename "$project")"
  done

  # Always exit 0 — init scripts must not fail container startup
  exit 0
}
```

## Canonical Path Gotcha

Claude derives the project identifier from the **git repository root**, not the cwd subdirectory. All subdirectories within the same git repo share one `~/.claude/projects/` entry.

Example: If `/workspace/claude/builder-project` is the git root, then:
- `cd /workspace/claude/builder-project && claude` → uses `workspace-claude-builder-project`
- `cd /workspace/claude/builder-project/src && claude` → same, `workspace-claude-builder-project`

`load-projects.sh` should canonicalize from the project's git root, not an arbitrary subdirectory.

## Error Handling

- **Missing memory directory** (`$project/.claude/memory/` doesn't exist): `2>/dev/null || true` handles gracefully — no files seeded, project still usable
- **Clone failure**: Log error, increment failure counter, continue with remaining projects
- **`cp -n` partial failure**: Non-fatal — some files may not seed but project is still accessible
- **Always exit 0**: Container startup must not be blocked by project seeding failures

## Integration with devcontainer.json

`postStartCommand` calls `load-projects.sh` last in the init chain:

```bash
sudo /usr/local/bin/init-firewall.sh && \
  /workspace/.devcontainer/scripts/init-ssh.sh && \
  /workspace/.devcontainer/scripts/init-gh-token.sh && \
  /workspace/.devcontainer/scripts/init-github-mcp.sh && \
  /workspace/.devcontainer/scripts/load-projects.sh sun2admin/builder-project
```

**Why this order matters:**
1. Firewall first — iptables rules block/allow egress before any network calls
2. SSH + gh-token before cloning — git auth must be ready before `clone_project()`
3. GitHub MCP binary before Claude — MCP server must exist before Claude starts
4. `load-projects.sh` last before Claude — projects must be seeded before Claude discovers them

## Behavior Under Different Conditions

| Condition | Cloning | Memory seeding | Result |
|---|---|---|---|
| First start (fresh devcontainerId) | Clones repos | Seeds all `memory/*.md` fresh | Full memory restored from git |
| Restart (same devcontainerId) | Skips (repos exist) | `cp -n` skips existing files | In-session writes preserved |
| Rebuild (new devcontainerId) | Clones again | Seeds all `memory/*.md` fresh | Full memory restored from git |
| No remote specified, local projects exist | N/A | Seeds all discovered projects | Works for pure-local setups |

## Alternative: autoMemoryDirectory

If you want to skip the seed/sync cycle entirely, set `autoMemoryDirectory` to write memory directly into the project repo:

```json
// ~/.claude/settings.json or .claude/settings.local.json
{
  "autoMemoryDirectory": "/workspace/claude/builder-project/.claude/memory"
}
```

When set, Claude writes auto-memory directly to the repo path — no seeding needed, memory is always in git. Trade-off: memory is committed on every write (noisier git history), and the setting cannot be in project-scoped `.claude/settings.json` due to a security restriction.

## Design Principles

1. **Memory-only seeding** — Only `memory/*.md` belongs in `~/.claude/projects/`. All other config is read from the repo directly.
2. **Non-destructive** — `cp -n` never overwrites. In-session writes always survive restarts.
3. **No wipe-and-reseed** — Never `rm -rf ~/.claude/projects/` before seeding. The named volume lifecycle (fresh on rebuild) handles cleanup automatically.
4. **Graceful failure** — Missing memory dirs, failed clones, or `cp` errors never block container startup.
5. **Idempotent** — Safe to call multiple times. Already-cloned repos are skipped. `cp -n` skips already-seeded files.
6. **Always exit 0** — Init scripts that fail would kill container startup. Log errors and continue.

## Files

- `/workspace/.devcontainer/scripts/load-projects.sh` — this script
- `/workspace/.devcontainer/devcontainer.json` — `postStartCommand` invocation
- `<project>/.claude/memory/*.md` — source of truth for seeded memory
- `~/.claude/projects/<canonical-path>/memory/` — seeding target (named volume)
