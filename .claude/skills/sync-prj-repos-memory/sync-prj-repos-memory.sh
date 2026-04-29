#!/bin/bash
# sync-prj-repos-memory — sync session memory from named volume back to git repo
# See SKILL.md for full documentation

set -euo pipefail

# ============================================================================
# Canonical path: replace / with - (leading dash intentional — matches Claude Code)
# Must produce identical output to load-projects.sh canonicalize_path()
# ============================================================================
canonicalize_path() {
  echo "${1%/}" | sed 's|/|-|g'
}

# ============================================================================
# Get authenticated GitHub username
# ============================================================================
get_authenticated_user() {
  gh whoami 2>/dev/null || echo ""
}

# ============================================================================
# Extract GitHub owner from git remote origin URL
# Returns 1 if no remote or URL unparseable
# ============================================================================
get_repo_owner() {
  local project_path=$1
  local remote_url
  remote_url=$(git -C "$project_path" config --get remote.origin.url 2>/dev/null || echo "")
  [[ -z "$remote_url" ]] && return 1
  echo "$remote_url" | sed -E 's|.*[:/]([^/]+)/[^/]+/?$|\1|'
}

# ============================================================================
# Sync memory from named volume → repo
# Uses rsync --delete if available; bash fallback otherwise
# Both approaches mirror the live state exactly, including deletions
# ============================================================================
sync_memory() {
  local project_root=$1
  local canonical_id
  canonical_id=$(canonicalize_path "$project_root")
  local live_memory="$HOME/.claude/projects/$canonical_id/memory"
  local repo_memory="$project_root/.claude/memory"

  if [[ ! -d "$live_memory" ]]; then
    echo "  No live memory found, skipping memory sync"
    return 0
  fi

  mkdir -p "$repo_memory"

  if command -v rsync &>/dev/null; then
    # rsync preferred: handles new, modified, and deleted files in one pass
    rsync -a --delete "$live_memory/" "$repo_memory/"
  else
    # Bash fallback for images without rsync (current container stack)
    # Step 1: copy new/modified files from live → repo
    cp -f "$live_memory"/*.md "$repo_memory/" 2>/dev/null || true
    # Step 2: remove files in repo not present in live (mirrors rsync --delete)
    for f in "$repo_memory"/*.md; do
      [[ -f "$live_memory/$(basename "$f")" ]] || rm -f "$f"
    done
  fi
}

# ============================================================================
# Stage all changes, commit with descriptive message, and push
# Uses git -C throughout — no cd, so cwd never changes
# ============================================================================
commit_project() {
  local project_root=$1

  # Stage everything: memory + any skills/commands/settings Claude wrote during session
  # settings.local.json is auto-gitignored and will never be staged
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

# ============================================================================
# Sync a single project: verify ownership, sync memory, commit and push
# ============================================================================
sync_project() {
  local project_root="${1%/}"
  local name
  name=$(basename "$project_root")

  echo "Syncing $name..."

  if [[ ! -d "$project_root/.git" ]]; then
    echo "✗ $name: not a git repository" >&2
    exit 1
  fi

  # Ownership check — only sync repos owned by the authenticated user
  local auth_user repo_owner
  auth_user=$(get_authenticated_user)

  if [[ -z "$auth_user" ]]; then
    echo "  ⚠ Could not verify ownership (gh whoami failed) — proceeding"
  else
    repo_owner=$(get_repo_owner "$project_root" 2>/dev/null || echo "")
    if [[ -n "$repo_owner" && "$repo_owner" != "$auth_user" ]]; then
      echo "⊘ $name: skipping (owner: $repo_owner, authenticated: $auth_user)"
      exit 0
    fi
  fi

  sync_memory "$project_root" || { echo "✗ $name: memory sync failed" >&2; exit 1; }
  commit_project "$project_root" || { echo "✗ $name: git commit/push failed" >&2; exit 1; }

  echo "✓ $name"
}

# ============================================================================
# Main: resolve project path and sync
# ============================================================================
main() {
  if [[ $# -gt 0 ]]; then
    # Explicit project path provided
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

main "$@"
