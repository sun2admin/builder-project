#!/bin/bash
# /build-stack — UX layer: gather user intent, write build.json, invoke tool.
# Composition logic lives in tools/build-stack/ (Python).
# Usage: build-stack.sh [--dry-run]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
BUILDS_DIR="${REPO_ROOT}/builds"
TOOL_DIR="${REPO_ROOT}/tools/build-stack"

source "${SKILL_DIR}/lib.sh"

[[ "${1:-}" == "--dry-run" ]] && export DRY_RUN=1 || export DRY_RUN=0

# State written into build.json
declare -A BUILD=(
  [BUILD_NAME]=""
  [AI_CLI]=""
  [PROJECT_REPO]=""        # may be empty string = sandbox
  [PLUGIN_REPOS]=""        # space-separated owner/repo entries
  [BASE_IMAGE_OVERRIDE]="" # null/empty = auto-pick
  [CREATED]=""
)

# ============================================================================
# Phase 1: Gather user intent
# ============================================================================

phase1_entry() {
  echo -e "${BLUE}=== /build-stack ===${NC}" >&2
  echo "Phase 1: Gather intent" >&2
  : "TODO: list existing builds, offer new/clone/modify"
  : "TODO: prompt build name with sanitization (lift from build-workspace)"
}

phase1_ai_cli() {
  : "TODO: menu — claude (default) | gemini"
  : "Set BUILD[AI_CLI]"
}

phase1_project_repo() {
  : "TODO: prompt — owner/repo OR empty=sandbox"
  : "Validate format if non-empty"
  : "Set BUILD[PROJECT_REPO]"
}

phase1_plugin_repos() {
  : "TODO: loop — prompt for plugin repos one at a time"
  : "Each: owner/repo or empty to finish"
  : "Optional source-repo prompt if GHCR image lacks OCI label"
  : "Set BUILD[PLUGIN_REPOS] (space-separated)"
}

phase1_overrides() {
  : "TODO: optional override prompts"
  : "  - base_image (offer after tool returns auto-pick? or before?)"
  : "  - credentials_delivery per detected cred"
  : "Note: L1 override actually requires aggregated analysis to validate."
  : "Likely flow: skill writes build.json with override=null,"
  : "tool computes auto-pick + emits available overrides,"
  : "skill re-prompts user for override choice, updates build.json, re-invokes tool."
}

# ============================================================================
# Phase 2: Validate + invoke tool
# ============================================================================

emit_build_json() {
  local out_path="$1"
  : "TODO: write build.json from BUILD[] state"
  : "Schema:"
  : "  schema_version, build_name, ai_cli, project_repo, plugin_repos[],"
  : "  overrides{base_image, additional_l4_features[], credentials_delivery{}},"
  : "  tool_min_version, created, last_modified"
}

invoke_tool() {
  local subcommand="$1"
  local json_path="$2"

  if [[ ! -d "$TOOL_DIR" ]]; then
    echo -e "${RED}Tool not installed at $TOOL_DIR${NC}" >&2
    echo "Run: pip install -e tools/build-stack/" >&2
    return 1
  fi

  run_cmd "python -m build_stack '$subcommand' '$json_path'"
}

phase2_invoke() {
  local name="${BUILD[BUILD_NAME]}"
  local dir="${BUILDS_DIR}/${name}"
  local json_path="${dir}/build.json"

  mkdir -p "$dir"
  emit_build_json "$json_path"

  invoke_tool validate "$json_path" || return 1
  invoke_tool compose  "$json_path" || return 1
}

# ============================================================================
# Entry
# ============================================================================

main() {
  phase1_entry
  phase1_ai_cli
  phase1_project_repo
  phase1_plugin_repos
  phase1_overrides
  phase2_invoke
}

main "$@"
