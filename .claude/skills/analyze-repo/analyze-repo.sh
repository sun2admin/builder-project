#!/bin/bash
# analyze-repo: thin wrapper for the build-stack tool's analyze subcommand.
# Phase 3 cutover: detection logic now lives in
# tools/build-stack/build_stack/analyzers/. This script preserves the skill's
# CLI contract (-q/--quiet, -v/--verbose, owner/repo) so existing callers
# (build-workflow, build-stack skill) keep working.
#
# stdout: path to analyzed_repos/<owner>/<repo>/analysis.json
# stderr: progress traces, plus markdown report when emitted

set -euo pipefail

RED=$'\033[0;31m'
NC=$'\033[0m'

read_input() {
  printf '%s' "$1" >&2
  read -r input
}

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"

QUIET=0
VERBOSE=0
REPO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -q|--quiet)   QUIET=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help)
      cat >&2 <<EOF
Usage: analyze-repo.sh [-q|--quiet] [-v|--verbose] [owner/repo]

  -q  Suppress markdown report on stderr (still saves analysis.md file).
  -v  Always emit markdown report regardless of TTY detection.
  Default: emit markdown to stderr only when stdout is a TTY.

stdout: path to analyzed_repos/<owner>/<repo>/analysis.json (single line)
stderr: progress traces, plus markdown report when emitted

Phase 3 cutover: this skill is now a thin wrapper for
\`python -m build_stack analyze\` — see tools/build-stack/.
EOF
      exit 0 ;;
    *) REPO="$1"; shift ;;
  esac
done

if [[ -z "$REPO" ]]; then
  read_input "GitHub repo (owner/repo): "
  REPO="$input"
fi

if [[ ! "$REPO" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]]; then
  echo -e "${RED}✘ Invalid format. Use owner/repo (e.g. sun2admin/myapp)${NC}" >&2
  exit 1
fi

FLAGS=()
[[ "$QUIET" == "1" ]] && FLAGS+=("-q")
[[ "$VERBOSE" == "1" ]] && FLAGS+=("-v")

cd "$REPO_ROOT"
exec python -m build_stack analyze "${FLAGS[@]}" "$REPO"
