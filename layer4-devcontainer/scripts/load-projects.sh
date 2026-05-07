#!/bin/bash

# load-projects.sh - Clone project repos and seed memory for the live project
#
# Usage: load-projects.sh [-live owner/repo] [owner/repo ...]
#
#   -live owner/repo  Clone to /workspace/claude/<name>, seed memory, write path
#                     to ~/live-project. Only one -live is allowed.
#   owner/repo        Clone to /workspace/repos/<name>. No memory seeding.
#
# If no -live is specified, ~/live-project is set to the claude home directory.
# Live repo clone failure is fatal. Non-live clone failure is a warning.

LIVE_WORKSPACE="/workspace/claude"
REPOS_WORKSPACE="/workspace/repos"
PROJECTS_BASE="$HOME/.claude/projects"
LIVE_PROJECT_FILE="$HOME/live-project"

live_repo=""
other_repos=()

# ============================================================================
# Canonicalize path to Claude Code project ID format
# Replaces all / with - (leading dash is intentional — matches Claude Code)
# ============================================================================
canonicalize_path() {
  echo "${1%/}" | sed 's|/|-|g'
}

# ============================================================================
# Clone a GitHub repo to target dir. Skip if already exists.
# ============================================================================
clone_repo() {
  local repo=$1 target=$2

  if [ -d "$target" ]; then
    echo "⊘ $(basename "$target"): already exists, skipping"
    return 0
  fi

  mkdir -p "$(dirname "$target")"
  git clone "https://github.com/$repo.git" "$target"
}

# ============================================================================
# Seed memory/*.md from repo into named volume (cp -n preserves runtime writes)
# ============================================================================
seed_memory() {
  local project_path=$1
  local canonical_id target_memory
  canonical_id=$(canonicalize_path "$project_path")
  target_memory="$PROJECTS_BASE/$canonical_id/memory"

  mkdir -p "$target_memory"

  if [ -d "$project_path/.claude/memory" ]; then
    cp -n "$project_path/.claude/memory"/*.md "$target_memory/" 2>/dev/null || true
  fi
}

# ============================================================================
# Parse -live flag and repo arguments
# ============================================================================
parse_args() {
  local live_count=0

  while [ $# -gt 0 ]; do
    case "$1" in
      -live)
        shift
        if [ $# -eq 0 ]; then
          echo "✗ -live requires a repo argument (e.g., -live owner/repo)" >&2
          exit 1
        fi
        live_count=$(( live_count + 1 ))
        if [ "$live_count" -gt 1 ]; then
          echo "✗ Only one -live repo is allowed" >&2
          exit 1
        fi
        live_repo="$1"
        ;;
      *)
        other_repos+=("$1")
        ;;
    esac
    shift
  done
}

# ============================================================================
# Main
# ============================================================================
main() {
  parse_args "$@"

  # Handle live project
  if [ -n "$live_repo" ]; then
    local live_name live_path
    live_name=$(echo "$live_repo" | cut -d'/' -f2)
    live_path="$LIVE_WORKSPACE/$live_name"

    echo "Cloning live project: $live_repo"
    clone_repo "$live_repo" "$live_path" || {
      echo "✗ Failed to clone live repo $live_repo — aborting" >&2
      exit 1
    }

    echo "Seeding memory: $live_name"
    seed_memory "$live_path"
    echo "$live_path" > "$LIVE_PROJECT_FILE"
    echo "✓ Live project: $live_path"
  else
    echo "$HOME" > "$LIVE_PROJECT_FILE"
    echo "⊘ No live project specified — Claude will start from home directory"
  fi

  # Clone non-live repos to /workspace/repos/
  if [ ${#other_repos[@]} -gt 0 ]; then
    mkdir -p "$REPOS_WORKSPACE"
    for repo in "${other_repos[@]}"; do
      local repo_name target
      repo_name=$(echo "$repo" | cut -d'/' -f2)
      target="$REPOS_WORKSPACE/$repo_name"
      echo "Cloning $repo..."
      clone_repo "$repo" "$target" || echo "⚠ Failed to clone $repo (non-fatal)"
    done
  fi
}

main "$@"

# Always exit with success — init scripts must not fail container startup
# Exception: live repo clone failure exits non-zero (handled in main above)
exit 0
