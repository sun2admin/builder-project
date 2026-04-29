#!/bin/bash
# sync-prj-repos-memory — sync session memory from named volume back to git repos
# See SKILL.md for full documentation

set -euo pipefail

WORKSPACE_ROOT="/workspace/claude"

synced=0
failed=0

# ============================================================================
# Canonical path: strip trailing slash, then leading slash, then replace / with -
# Must produce identical output to load-projects.sh canonicalize_path()
# ============================================================================
canonicalize_path() {
  echo "${1%/}" | sed 's|/|-|g'
}

# ============================================================================
# Traverse up from a directory until .git/ is found; print the git root
# ============================================================================
find_git_root() {
  local dir="${1:-$PWD}"
  while [[ "$dir" != "/" ]]; do
    [[ -d "$dir/.git" ]] && echo "$dir" && return 0
    dir=$(dirname "$dir")
  done
  return 1
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

  # Skip gracefully if no live memory exists for this project
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
# Uses git -C throughout — no cd, so no cwd state leaks between projects
# ============================================================================
commit_project() {
  local project_root=$1

  # Stage everything: memory + any skills/commands/settings Claude wrote during session
  # settings.local.json is auto-gitignored and will never be staged
  git -C "$project_root" add -A

  # Nothing to commit — not an error
  if git -C "$project_root" diff --cached --quiet; then
    echo "  Nothing to sync"
    return 0
  fi

  # Build descriptive commit message with change counts
  local modified added deleted
  modified=$(git -C "$project_root" diff --cached --name-only --diff-filter=M | wc -l | tr -d ' ')
  added=$(git -C "$project_root" diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
  deleted=$(git -C "$project_root" diff --cached --name-only --diff-filter=D | wc -l | tr -d ' ')

  git -C "$project_root" commit -m "sync-prj-repos-memory: Sync memory and config (modified $modified, added $added, deleted $deleted)"

  # Detect branch and push
  local branch
  branch=$(git -C "$project_root" rev-parse --abbrev-ref HEAD)
  git -C "$project_root" push origin "$branch"
}

# ============================================================================
# Sync a single project: memory then commit
# ============================================================================
sync_project() {
  local project_root="${1%/}"  # strip trailing slash defensively
  local name
  name=$(basename "$project_root")

  echo "Syncing $name..."

  if [[ ! -d "$project_root/.git" ]]; then
    echo "✗ $name: not a git repository, skipping"
    ((++failed))
    return 1
  fi

  sync_memory "$project_root" || { echo "✗ $name: memory sync failed"; ((++failed)); return 1; }
  commit_project "$project_root" || { echo "✗ $name: git commit/push failed"; ((++failed)); return 1; }

  echo "✓ $name"
  ((++synced))
}

# ============================================================================
# Main: determine scope and dispatch
# ============================================================================
main() {
  if [[ $# -gt 0 ]]; then
    # Explicit project path provided
    sync_project "$1"

  elif find_git_root "$PWD" &>/dev/null; then
    # Inside a git repo — sync current project only
    local project_root
    project_root=$(find_git_root "$PWD")
    sync_project "$project_root"

  else
    # Outside any git repo — sync all projects under /workspace/claude/
    echo "Syncing all projects in $WORKSPACE_ROOT..."
    echo ""
    for subdir in "$WORKSPACE_ROOT"/*/; do
      [[ -d "${subdir}.claude" ]] || continue
      sync_project "$subdir"
    done
  fi

  echo ""
  echo "Done: $synced synced, $failed failed"
}

main "$@"
