#!/bin/bash
# /build-stack — UX layer: gather user intent, write build.json, invoke tool.
# Composition logic lives in tools/build-stack/ (Python).
# Usage: build-stack.sh [--dry-run]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
BUILDS_DIR="${REPO_ROOT}/builds"
ANALYZED_DIR="${REPO_ROOT}/analyzed_repos"
ANALYZE_SH="${REPO_ROOT}/.claude/skills/analyze-repo/analyze-repo.sh"

source "${SKILL_DIR}/lib.sh"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
export DRY_RUN

# State collected by Phase 1 prompts
PROJECT_REPO=""           # "" = sandbox
BUILD_CATEGORY=""
BUILD_PROJECT=""
declare -a AI_CLIS=()     # ordered: index 0 is primary
declare -a PLUGIN_SELECTIONS=()    # entries: "<marketplace>|<plugin>|<category>"
USE_RECOMMENDED_L3=0
GITHUB_USER=""

# ============================================================================
# Pre-flight
# ============================================================================

preflight() {
  command -v git >/dev/null 2>&1 || {
    echo -e "${RED}git not in PATH${NC}" >&2
    exit 1
  }
  command -v gh >/dev/null 2>&1 || {
    echo -e "${RED}gh CLI not in PATH${NC}" >&2
    exit 1
  }
  gh auth status >/dev/null 2>&1 || {
    echo -e "${RED}Not authenticated. Run: gh auth login${NC}" >&2
    exit 1
  }
  python -m build_stack --help >/dev/null 2>&1 || {
    echo -e "${RED}Tool not installed. Run: pip install -e tools/build-stack/${NC}" >&2
    exit 1
  }
  GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null) || {
    echo -e "${RED}Failed to query gh user${NC}" >&2
    exit 1
  }
}

# ============================================================================
# Helpers
# ============================================================================

# Sanitize project/build identifier: lowercase, non-alnum to hyphen, collapse, trim.
sanitize_name() {
  local raw="$1"
  raw=$(echo "$raw" | tr '[:upper:]' '[:lower:]')
  raw=$(echo "$raw" | sed -E 's/[^a-z0-9_-]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')
  echo "$raw"
}

# Validate a GH repo. Returns:
#   0 = exists
#   1 = 404 (typo, reprompt)
#   2 = auth/network error (hard-fail)
gh_repo_check() {
  local repo="$1"
  local out rc
  out=$(gh api "repos/${repo}" 2>&1) && return 0
  rc=$?
  if echo "$out" | grep -qiE 'not found|HTTP 404'; then
    return 1
  fi
  echo -e "${RED}gh api error for ${repo}: ${out}${NC}" >&2
  return 2
}

# Days since file mtime (integer).
mtime_days() {
  local f="$1"
  local now mtime
  now=$(date +%s)
  mtime=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo "$now")
  echo $(( (now - mtime) / 86400 ))
}

# Run analyze-repo subprocess. stdout = analysis.json path; stderr passes through.
# Returns analyze-repo's exit code.
run_analyze() {
  local repo="$1"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] analyze-repo ${repo}${NC}" >&2
    return 0
  fi
  bash "$ANALYZE_SH" -q "$repo"
}

# Cache-or-analyze. Returns 0 on success (cached or freshly analyzed), 1 on
# user quit, 2 on analyze failure (caller decides retry).
cache_or_analyze() {
  local repo="$1"
  local cache="${ANALYZED_DIR}/${repo}/analysis.json"
  if [[ -f "$cache" ]]; then
    local age
    age=$(mtime_days "$cache")
    echo "" >&2
    echo "Cache hit: ${cache} (${age} days old)" >&2
    echo "  [1] use cached  (default)" >&2
    echo "  [2] reanalyze" >&2
    while true; do
      read_input "Selection [1]: "
      local sel="${input:-1}"
      case "$sel" in
        1) return 0 ;;
        2) break ;;
        q) return 1 ;;
        *) echo -e "${RED}Invalid.${NC}" >&2 ;;
      esac
    done
  fi
  if run_analyze "$repo" >/dev/null; then
    return 0
  fi
  return 2
}

# Analyze loop with failure menu. Mode "project" => [r]/[n]/[q]; "plugin" => [r]/[s]/[q].
# Sets ANALYZE_RESULT to: ok | new_name | skip | quit
analyze_with_menu() {
  local repo="$1"
  local mode="$2"
  while true; do
    local rc=0
    cache_or_analyze "$repo" || rc=$?
    case $rc in
      0) ANALYZE_RESULT="ok"; return 0 ;;
      1) ANALYZE_RESULT="quit"; return 0 ;;
      2)
        echo "" >&2
        echo -e "${YELLOW}Analyze failed for ${repo}.${NC}" >&2
        if [[ "$mode" == "project" ]]; then
          echo "  [r] retry" >&2
          echo "  [n] new name" >&2
          echo "  [q] quit" >&2
          while true; do
            read_input "Selection: "
            case "$input" in
              r) break ;;
              n) ANALYZE_RESULT="new_name"; return 0 ;;
              q) ANALYZE_RESULT="quit"; return 0 ;;
              *) echo -e "${RED}Invalid.${NC}" >&2 ;;
            esac
          done
        else
          echo "  [r] retry" >&2
          echo "  [s] skip" >&2
          echo "  [q] quit" >&2
          while true; do
            read_input "Selection: "
            case "$input" in
              r) break ;;
              s) ANALYZE_RESULT="skip"; return 0 ;;
              q) ANALYZE_RESULT="quit"; return 0 ;;
              *) echo -e "${RED}Invalid.${NC}" >&2 ;;
            esac
          done
        fi
        ;;
    esac
  done
}

# Probe analysis.json for AI CLI signals. Sets DETECTED_CLAUDE / DETECTED_GEMINI.
detect_ai_signals() {
  DETECTED_CLAUDE=0
  DETECTED_GEMINI=0
  [[ -z "$PROJECT_REPO" ]] && return 0
  local cache="${ANALYZED_DIR}/${PROJECT_REPO}/analysis.json"
  [[ -f "$cache" ]] || return 0

  if jq -e '(.claude_plugins // []) | length > 0' "$cache" >/dev/null 2>&1; then
    DETECTED_CLAUDE=1
  fi
  if jq -e '(.mcp_servers // []) | map(.name? // "") | map(ascii_downcase) | any(test("claude"))' "$cache" >/dev/null 2>&1; then
    DETECTED_CLAUDE=1
  fi
  if jq -e '(.mcp_servers // []) | map(.name? // "") | map(ascii_downcase) | any(test("gemini"))' "$cache" >/dev/null 2>&1; then
    DETECTED_GEMINI=1
  fi
  if jq -e '(.libraries.node // []) | any(test("gemini"; "i"))' "$cache" >/dev/null 2>&1; then
    DETECTED_GEMINI=1
  fi
}

# ============================================================================
# Phase 1 steps
# ============================================================================

step1_project_repo() {
  while true; do
    echo "" >&2
    read_input "Project repo (owner/repo, empty = sandbox): "
    local raw="${input:-}"
    if [[ -z "$raw" ]]; then
      PROJECT_REPO=""
      return 0
    fi
    if [[ ! "$raw" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
      echo -e "${RED}Invalid format. Use owner/repo.${NC}" >&2
      continue
    fi
    local rc=0
    gh_repo_check "$raw" || rc=$?
    case $rc in
      0) PROJECT_REPO="$raw"; return 0 ;;
      1) echo -e "${YELLOW}Repo ${raw} not found (404). Try again.${NC}" >&2 ;;
      2) exit 1 ;;
    esac
  done
}

step2_analyze_project() {
  [[ -z "$PROJECT_REPO" ]] && return 0
  if [[ $DRY_RUN -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] skip analyze for ${PROJECT_REPO}${NC}" >&2
    return 0
  fi
  while true; do
    analyze_with_menu "$PROJECT_REPO" "project"
    case "$ANALYZE_RESULT" in
      ok)       return 0 ;;
      quit)     echo "Exiting." >&2; exit 0 ;;
      new_name) step1_project_repo ;;
    esac
  done
}

step3_category() {
  local default
  if [[ -n "$PROJECT_REPO" ]]; then
    default="${PROJECT_REPO%%/*}"
  else
    default="$GITHUB_USER"
  fi
  while true; do
    echo "" >&2
    read_input "Build category [${default}]: "
    local raw="${input:-$default}"
    local sanitized
    sanitized=$(sanitize_name "$raw")
    if [[ -n "$sanitized" ]]; then
      BUILD_CATEGORY="$sanitized"
      return 0
    fi
    echo -e "${RED}Category cannot be empty.${NC}" >&2
  done
}

# Find first free slot under builds/<CATEGORY>/.
# Sets CANDIDATE_BASE, CANDIDATE_FREE (e.g. career-ops or career-ops-3),
# COLLISION (0/1).
collision_check() {
  local base
  if [[ -n "$PROJECT_REPO" ]]; then
    base=$(sanitize_name "${PROJECT_REPO##*/}")
  else
    base="sandbox"
  fi
  CANDIDATE_BASE="$base"
  local cat_dir="${BUILDS_DIR}/${BUILD_CATEGORY}"
  if [[ ! -d "${cat_dir}/${base}" ]]; then
    CANDIDATE_FREE="$base"
    COLLISION=0
    return 0
  fi
  local n=2
  while [[ -d "${cat_dir}/${base}-${n}" ]]; do
    n=$((n + 1))
  done
  CANDIDATE_FREE="${base}-${n}"
  COLLISION=1
}

step5_project_name() {
  collision_check
  if [[ $COLLISION -eq 0 ]]; then
    while true; do
      echo "" >&2
      read_input "Project name [${CANDIDATE_FREE}]: "
      local raw="${input:-$CANDIDATE_FREE}"
      local sanitized
      sanitized=$(sanitize_name "$raw")
      if [[ -z "$sanitized" ]]; then
        echo -e "${RED}Name cannot be empty.${NC}" >&2
        continue
      fi
      if [[ "$sanitized" != "$CANDIDATE_FREE" && -d "${BUILDS_DIR}/${BUILD_CATEGORY}/${sanitized}" ]]; then
        BUILD_PROJECT="$sanitized"
        CANDIDATE_BASE="$sanitized"
        collision_recurse
        return 0
      fi
      BUILD_PROJECT="$sanitized"
      OVERWRITE=0
      return 0
    done
  fi
  collision_menu
}

# Display the 3-option collision menu using current CANDIDATE_BASE/CANDIDATE_FREE.
collision_menu() {
  while true; do
    echo "" >&2
    echo -e "${YELLOW}Project name conflict in builds/${BUILD_CATEGORY}/${NC}" >&2
    echo "  [1] ${CANDIDATE_FREE}  (default)" >&2
    echo "  [2] overwrite ${CANDIDATE_BASE}" >&2
    echo "  [3] custom name" >&2
    read_input "Selection [1]: "
    local sel="${input:-1}"
    case "$sel" in
      1) BUILD_PROJECT="$CANDIDATE_FREE"; OVERWRITE=0; return 0 ;;
      2) BUILD_PROJECT="$CANDIDATE_BASE"; OVERWRITE=1; return 0 ;;
      3) collision_recurse; return 0 ;;
      q) echo "Exiting." >&2; exit 0 ;;
      *) echo -e "${RED}Invalid.${NC}" >&2 ;;
    esac
  done
}

# Free-text reprompt; recurses into collision_menu if name collides.
collision_recurse() {
  while true; do
    echo "" >&2
    read_input "Custom project name: "
    local raw="${input:-}"
    local sanitized
    sanitized=$(sanitize_name "$raw")
    if [[ -z "$sanitized" ]]; then
      echo -e "${RED}Name cannot be empty.${NC}" >&2
      continue
    fi
    if [[ -d "${BUILDS_DIR}/${BUILD_CATEGORY}/${sanitized}" ]]; then
      CANDIDATE_BASE="$sanitized"
      local n=2
      while [[ -d "${BUILDS_DIR}/${BUILD_CATEGORY}/${sanitized}-${n}" ]]; do
        n=$((n + 1))
      done
      CANDIDATE_FREE="${sanitized}-${n}"
      collision_menu
      return 0
    fi
    BUILD_PROJECT="$sanitized"
    OVERWRITE=0
    return 0
  done
}

step6_ai_clis() {
  local available_json
  available_json=$(python -m build_stack list-ai-clis --json 2>/dev/null) || {
    echo -e "${RED}Failed to query list-ai-clis${NC}" >&2
    exit 1
  }
  local available
  mapfile -t available < <(echo "$available_json" | jq -r '.[]')

  detect_ai_signals

  declare -A selected=()
  declare -a order=()
  # Default: claude pre-selected; if signals point to gemini also, still
  # primary stays claude per spec ("Default selected: claude").
  selected[claude]=1
  order=("claude")

  while true; do
    echo "" >&2
    echo -e "${BLUE}AI CLI selection${NC}" >&2
    [[ -n "$PROJECT_REPO" ]] && echo "  Detected signals: claude=${DETECTED_CLAUDE} gemini=${DETECTED_GEMINI}" >&2
    local i=1
    declare -a idx_to_cli=()
    for cli in "${available[@]}"; do
      local mark=" "
      local tag=""
      if [[ -n "${selected[$cli]:-}" ]]; then
        mark="x"
        if [[ "${order[0]:-}" == "$cli" ]]; then
          tag="  (primary)"
        fi
      fi
      echo "  [${mark}] ${i}) ${cli}${tag}" >&2
      idx_to_cli+=("$cli")
      i=$((i + 1))
    done
    echo "  [s] submit" >&2
    echo "  [q] quit" >&2
    read_input "Selection: "
    local sel="${input:-}"
    case "$sel" in
      q) echo "Exiting." >&2; exit 0 ;;
      s)
        if [[ ${#order[@]} -eq 0 ]]; then
          echo -e "${RED}Select at least one CLI before submit.${NC}" >&2
          continue
        fi
        AI_CLIS=("${order[@]}")
        return 0
        ;;
      *)
        if [[ ! "$sel" =~ ^[0-9]+$ ]] || [[ $sel -lt 1 || $sel -gt ${#idx_to_cli[@]} ]]; then
          echo -e "${RED}Invalid.${NC}" >&2
          continue
        fi
        local pick="${idx_to_cli[$((sel - 1))]}"
        if [[ -n "${selected[$pick]:-}" ]]; then
          unset 'selected[$pick]'
          local new_order=()
          for c in "${order[@]}"; do
            [[ "$c" != "$pick" ]] && new_order+=("$c")
          done
          order=("${new_order[@]}")
        else
          selected[$pick]=1
          order+=("$pick")
        fi
        ;;
    esac
  done
}

step7_recommended_prompt() {
  local rec_file="${REPO_ROOT}/tools/build-stack/build_stack/data/recommended-plugins.json"
  echo "" >&2
  echo -e "${BLUE}Recommended L3${NC}" >&2

  if [[ ! -f "$rec_file" ]]; then
    echo -e "${YELLOW}recommended-plugins.json missing — defaulting to no.${NC}" >&2
    USE_RECOMMENDED_L3=0
    return 0
  fi
  local count
  count=$(jq '.plugins | length' "$rec_file")
  if [[ "$count" -eq 0 ]]; then
    echo -e "${YELLOW}recommended-plugins.json is empty — defaulting to no.${NC}" >&2
    USE_RECOMMENDED_L3=0
    return 0
  fi

  echo "Recommended set ($count plugins):" >&2
  jq -r '.plugins[] | "  - \(.marketplace) :: \(.plugin)"' "$rec_file" >&2
  echo "" >&2
  read_input "Include recommended plugins (base on recommended L3)? [y/N]: "
  case "${input:-}" in
    y|Y) USE_RECOMMENDED_L3=1; echo -e "${GREEN}✓ recommended L3 enabled${NC}" >&2 ;;
    *)   USE_RECOMMENDED_L3=0; echo -e "${CYAN}skipping recommended L3 (build off L2)${NC}" >&2 ;;
  esac
}

step8_plugin_selector() {
  echo "" >&2
  echo -e "${BLUE}Additional plugins${NC}" >&2
  read_input "Pick additional plugins via marketplace selector? [y/N]: "
  case "${input:-}" in
    y|Y) ;;
    *) echo -e "${CYAN}skipping plugin selector${NC}" >&2; return 0 ;;
  esac

  local selector_lib="${REPO_ROOT}/.claude/skills/_lib/plugin-selector.sh"
  if [[ ! -f "$selector_lib" ]]; then
    echo -e "${RED}selector lib missing: $selector_lib${NC}" >&2
    return 0
  fi
  # shellcheck disable=SC1090
  source "$selector_lib"

  local out_file
  out_file=$(mktemp)
  local exclude_flag=()
  [[ "$USE_RECOMMENDED_L3" == "1" ]] && exclude_flag+=(--exclude-recommended)

  if ! plugin_selector_run --mode build-stack "${exclude_flag[@]}" --out "$out_file"; then
    echo -e "${CYAN}no additional plugins selected${NC}" >&2
    rm -f "$out_file"
    return 0
  fi
  local picked
  picked=$(jq 'length' "$out_file")
  if [[ "$picked" -eq 0 ]]; then
    rm -f "$out_file"
    return 0
  fi
  while IFS=$'\t' read -r mkt plugin cat; do
    [[ -z "$mkt" || -z "$plugin" ]] && continue
    PLUGIN_SELECTIONS+=("$mkt|$plugin|$cat")
  done < <(jq -r '.[] | [.marketplace, .plugin, (.category // "null")] | @tsv' "$out_file")
  rm -f "$out_file"
  echo -e "${GREEN}✓ ${#PLUGIN_SELECTIONS[@]} plugin(s) added${NC}" >&2
}

# ============================================================================
# build.json emission
# ============================================================================

json_array() {
  # Echo a JSON array of the (possibly zero) arguments.
  if [[ $# -eq 0 ]]; then
    echo '[]'
  else
    printf '%s\n' "$@" | jq -R . | jq -s .
  fi
}

emit_build_json() {
  local out_path="$1"
  local project_repo_arg=""
  [[ -n "$PROJECT_REPO" ]] && project_repo_arg="$PROJECT_REPO"

  local clis_json
  clis_json=$(json_array "${AI_CLIS[@]:-}")
  clis_json=$(echo "$clis_json" | jq '[.[] | select(. != "")]')

  local selections_json="[]"
  if [[ ${#PLUGIN_SELECTIONS[@]} -gt 0 ]]; then
    local entries=()
    local s
    for s in "${PLUGIN_SELECTIONS[@]}"; do
      local mkt="${s%%|*}"
      local rest="${s#*|}"
      local plugin="${rest%%|*}"
      local cat="${rest##*|}"
      local cat_json
      if [[ "$cat" == "null" || -z "$cat" ]]; then
        cat_json="null"
      else
        cat_json=$(jq -n --arg c "$cat" '$c')
      fi
      entries+=("$(jq -n --arg m "$mkt" --arg p "$plugin" --argjson c "$cat_json" \
        '{marketplace: $m, plugin: $p, category: $c}')")
    done
    selections_json=$(printf '%s\n' "${entries[@]}" | jq -s '.')
  fi

  local use_rec="false"
  [[ "$USE_RECOMMENDED_L3" == "1" ]] && use_rec="true"

  jq -n \
    --arg category "$BUILD_CATEGORY" \
    --arg project  "$BUILD_PROJECT" \
    --arg repo     "$project_repo_arg" \
    --argjson selections "$selections_json" \
    --argjson clis "$clis_json" \
    --argjson use_rec "$use_rec" \
    '{
      schema_version: 3,
      build_category: $category,
      build_project: $project,
      project_repo: (if $repo == "" then null else $repo end),
      ai_clis: $clis,
      use_recommended_l3: $use_rec,
      plugin_selections: $selections
    }' > "$out_path"
}

# ============================================================================
# Phase 2: stage + invoke tool
# ============================================================================

phase2_invoke() {
  mkdir -p "${BUILDS_DIR}/.staging"
  local stage_dir
  stage_dir=$(mktemp -d "${BUILDS_DIR}/.staging/stage.XXXXXX")
  trap 'rm -rf "$stage_dir"' EXIT

  local build_json="${stage_dir}/build.json"
  emit_build_json "$build_json"

  echo "" >&2
  echo "Validating build.json..." >&2
  ( cd "$REPO_ROOT" && python -m build_stack validate "$build_json" ) || {
    echo -e "${RED}Validate failed.${NC}" >&2
    exit 1
  }

  echo "Composing stack..." >&2
  ( cd "$REPO_ROOT" && python -m build_stack compose "$build_json" ) || {
    echo -e "${RED}Compose failed.${NC}" >&2
    exit 1
  }

  local final_dir="${BUILDS_DIR}/${BUILD_CATEGORY}/${BUILD_PROJECT}"
  mkdir -p "${BUILDS_DIR}/${BUILD_CATEGORY}"
  if [[ "${OVERWRITE:-0}" -eq 1 && -d "$final_dir" ]]; then
    rm -rf "$final_dir"
  fi
  mv "$stage_dir" "$final_dir"
  trap - EXIT
  FINAL_DIR="$final_dir"
}

# ============================================================================
# Phase 9: summary
# ============================================================================

print_summary() {
  local final_rel="builds/${BUILD_CATEGORY}/${BUILD_PROJECT}"
  echo "" >&2
  echo -e "${GREEN}✓ Build composed: ${final_rel}/${NC}" >&2
  echo "" >&2
  echo "Inputs:" >&2
  echo "  Project repo: ${PROJECT_REPO:-sandbox}" >&2
  if [[ "$USE_RECOMMENDED_L3" == "1" ]]; then
    echo "  Recommended L3: yes" >&2
  else
    echo "  Recommended L3: no (build off L2)" >&2
  fi
  if [[ ${#PLUGIN_SELECTIONS[@]} -eq 0 ]]; then
    echo "  Additional plugins: (none)" >&2
  else
    local s
    for s in "${PLUGIN_SELECTIONS[@]}"; do
      local mkt="${s%%|*}"
      local rest="${s#*|}"
      local plugin="${rest%%|*}"
      echo "    - ${plugin} (${mkt})" >&2
    done
  fi
  echo "  AI CLIs: ${AI_CLIS[*]}" >&2

  local agg="${FINAL_DIR}/aggregated.json"
  local l1="?" l3="none"
  if [[ -f "$agg" ]]; then
    l1=$(jq -r '.l1_pick // .l1_variant // "?"' "$agg" 2>/dev/null || echo "?")
    l3=$(jq -r '.l3_pick.image // "none"' "$agg" 2>/dev/null || echo "none")
  fi
  echo "" >&2
  echo "Picks:" >&2
  echo "  L1: ${l1}" >&2
  echo "  L2: ${AI_CLIS[0]}" >&2
  echo "  L3: ${l3}" >&2
  echo "" >&2
  echo "Outputs written:" >&2
  echo "  ${final_rel}/build.json" >&2
  echo "  ${final_rel}/aggregated.json" >&2
  echo "  ${final_rel}/devcontainer.json" >&2
  echo "  ${final_rel}/workspace.env" >&2
  echo "" >&2
  echo "Next: cp ${final_rel}/devcontainer.json .devcontainer/" >&2
}

# ============================================================================
# Entry
# ============================================================================

main() {
  echo -e "${BLUE}=== /build-stack ===${NC}" >&2
  [[ $DRY_RUN -eq 1 ]] && echo -e "${YELLOW}[DRY-RUN MODE] no analyze, no staging, no tool calls${NC}" >&2

  preflight

  step1_project_repo
  step2_analyze_project
  step3_category
  step5_project_name
  step6_ai_clis
  step7_recommended_prompt
  step8_plugin_selector

  if [[ $DRY_RUN -eq 1 ]]; then
    local tmp
    tmp=$(mktemp)
    BUILD_PROJECT="${BUILD_PROJECT:-${CANDIDATE_FREE}}"
    emit_build_json "$tmp"
    cat "$tmp"
    rm -f "$tmp"
    exit 0
  fi

  phase2_invoke
  print_summary
}

main "$@"
