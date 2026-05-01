#!/bin/bash
# /build-workspace — Master orchestrator
# Lists existing builds, runs layer wizard, writes workspace.env, launches Claude
# Usage: build-workspace.sh [--dry-run]

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
BUILDS_DIR="${REPO_ROOT}/builds"

source "${SKILL_DIR}/lib.sh"

[[ "${1:-}" == "--dry-run" ]] && export DRY_RUN=1 || export DRY_RUN=0

# State
declare -A BUILD=(
  [BASE_IMAGE]=""
  [AI_INSTALL]=""
  [PLUGIN_LAYER]=""
  [PROJECT_SELECTED]=""
  [WORKSPACE_DIR]=""
  [CREATED]=""
)
BUILD_NAME=""

# ============================================================================
# Helpers
# ============================================================================

run_layer() {
  local script="$1"
  shift
  local args=("$@")
  # Display (stderr) goes to terminal; stdout (selection) captured by caller
  DRY_RUN=$DRY_RUN bash "$script" "${args[@]}" 2>/dev/tty
}

load_build() {
  local name="$1"
  local env_file="${BUILDS_DIR}/${name}/workspace.env"
  [[ -f "$env_file" ]] || return 1

  while IFS='=' read -r key val; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    BUILD[$key]="$val"
  done < "$env_file"
}

save_build() {
  local name="$1"
  local dir="${BUILDS_DIR}/${name}"
  mkdir -p "$dir"

  local now
  now=$(date +%Y-%m-%d)
  [[ -z "${BUILD[CREATED]}" ]] && BUILD[CREATED]="$now"

  cat > "${dir}/workspace.env" << EOF
BASE_IMAGE=${BUILD[BASE_IMAGE]}
AI_INSTALL=${BUILD[AI_INSTALL]}
PLUGIN_LAYER=${BUILD[PLUGIN_LAYER]}
PROJECT_SELECTED=${BUILD[PROJECT_SELECTED]}
WORKSPACE_DIR=${BUILD[WORKSPACE_DIR]}
CREATED=${BUILD[CREATED]}
LAST_MODIFIED=${now}
EOF
  echo -e "${GREEN}✓ Saved: builds/${name}/workspace.env${NC}" >&2
}

prompt_build_name() {
  local default="${1:-}"
  local prompt="Build name"
  [[ -n "$default" ]] && prompt+=" [${default}]"
  prompt+=": "

  while true; do
    read_input "$prompt"
    local name="${input:-$default}"
    name=$(echo "$name" | tr ' ' '-' | tr -cd 'a-zA-Z0-9_-')
    if [[ -n "$name" ]]; then
      echo "$name"
      return 0
    fi
    echo -e "${RED}Name cannot be empty.${NC}" >&2
  done
}

# ============================================================================
# Entry: List existing builds (Option A flow)
# ============================================================================

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              /build-workspace                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
[[ $DRY_RUN -eq 1 ]] && echo -e "${YELLOW}[DRY-RUN MODE]${NC}"
echo ""

# Check GitHub auth
GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null) || {
  echo -e "${RED}✘ Not authenticated with GitHub. Run: gh auth login${NC}"
  exit 1
}

mkdir -p "$BUILDS_DIR"
mapfile -t EXISTING < <(find "$BUILDS_DIR" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; | sort)

if [[ ${#EXISTING[@]} -eq 0 ]]; then
  echo "No saved builds found. Starting new build."
  echo ""
  BUILD_NAME=$(prompt_build_name)
else
  echo "Saved builds:"
  echo ""
  for i in "${!EXISTING[@]}"; do
    num=$((i + 1))
    name="${EXISTING[$i]}"
    # Show summary if workspace.env exists
    if [[ -f "${BUILDS_DIR}/${name}/workspace.env" ]]; then
      ai=$(grep "^AI_INSTALL=" "${BUILDS_DIR}/${name}/workspace.env" | cut -d= -f2)
      base=$(grep "^BASE_IMAGE=" "${BUILDS_DIR}/${name}/workspace.env" | cut -d= -f2)
      modified=$(grep "^LAST_MODIFIED=" "${BUILDS_DIR}/${name}/workspace.env" | cut -d= -f2)
      echo "  $num) ${name}  [${ai} / ${base} — ${modified}]"
    else
      echo "  $num) ${name}"
    fi
  done
  echo ""
  echo "  n) new build"
  echo "  q) quit"
  echo ""

  while true; do
    input_selection "Selection: " "^[0-9]+$|^[nq]$"
    case $? in
      0)
        case "$SELECTION" in
          n) BUILD_NAME=$(prompt_build_name); break ;;
          q) echo "Exiting."; exit 0 ;;
          [0-9]*)
            if [[ $SELECTION -ge 1 && $SELECTION -le ${#EXISTING[@]} ]]; then
              SELECTED_BUILD="${EXISTING[$((SELECTION - 1))]}"
              echo ""
              echo "  c) clone as new build"
              echo "  m) modify in place"
              echo "  b) back"
              echo "  q) quit"
              echo ""
              while true; do
                input_selection "Action: " "^[cmbq]$"
                case $? in
                  0) case "$SELECTION" in
                       c)
                         load_build "$SELECTED_BUILD"
                         BUILD[CREATED]=""  # reset so save_build sets a new created date
                         BUILD_NAME=$(prompt_build_name "$SELECTED_BUILD-copy")
                         break 2
                         ;;
                       m)
                         load_build "$SELECTED_BUILD"
                         BUILD_NAME="$SELECTED_BUILD"
                         break 2
                         ;;
                       b) break ;;
                       q) echo "Exiting."; exit 0 ;;
                     esac ;;
                  1) [[ ! -t 0 ]] && exit 1 ;;
                  2) exit 0 ;;
                esac
              done
            else
              echo -e "${RED}Invalid selection.${NC}"
            fi
            ;;
        esac
        ;;
      1) [[ ! -t 0 ]] && exit 1 ;;
      2) exit 0 ;;
    esac
  done
fi

echo ""
echo -e "${BLUE}Build: ${BUILD_NAME}${NC}"
echo ""

# ============================================================================
# Layer wizard with back navigation
# ============================================================================

LAYER_IDX=0

call_layer() {
  local idx="$1"
  case $idx in
    0)
      result=$(run_layer "${SKILL_DIR}/../build-layer1/build-layer1.sh" "${BUILD[BASE_IMAGE]}")
      ;;
    1)
      result=$(run_layer "${SKILL_DIR}/../build-layer2/build-layer2.sh" "${BUILD[AI_INSTALL]}")
      ;;
    2)
      result=$(run_layer "${SKILL_DIR}/../build-layer3/build-layer3.sh" "${BUILD[AI_INSTALL]}" "${BUILD[PLUGIN_LAYER]}")
      ;;
    3)
      result=$(run_layer "${SKILL_DIR}/../build-layer4/build-layer4.sh" "${BUILD[AI_INSTALL]}" "${BUILD[PROJECT_SELECTED]}")
      ;;
  esac
}

while [[ $LAYER_IDX -ge 0 && $LAYER_IDX -lt 4 ]]; do
  result=""
  call_layer $LAYER_IDX
  rc=$?

  case $rc in
    0)
      case $LAYER_IDX in
        0) BUILD[BASE_IMAGE]="$result" ;;
        1) BUILD[AI_INSTALL]="$result" ;;
        2) BUILD[PLUGIN_LAYER]="$result" ;;
        3)
          BUILD[WORKSPACE_DIR]="$result"
          # Extract project repo from workspace path
          BUILD[PROJECT_SELECTED]="${result##/workspace/${BUILD[AI_INSTALL]}/}"
          [[ "${BUILD[PROJECT_SELECTED]}" == "${result}" ]] && BUILD[PROJECT_SELECTED]=""
          ;;
      esac
      ((LAYER_IDX++))
      ;;
    1) echo -e "\n${YELLOW}Exiting.${NC}"; exit 0 ;;
    2) [[ $LAYER_IDX -gt 0 ]] && ((LAYER_IDX--)) ;;
  esac
done

# ============================================================================
# Summary and confirm
# ============================================================================

echo ""
echo -e "${BLUE}=== Summary ===${NC}"
echo "  Build name:   ${BUILD_NAME}"
echo "  Base image:   ${BUILD[BASE_IMAGE]}"
echo "  AI CLI:       ${BUILD[AI_INSTALL]}"
echo "  Plugin layer: ${BUILD[PLUGIN_LAYER]}"
echo "  Project:      ${BUILD[PROJECT_SELECTED]:-"(none)"}"
echo "  Workspace:    ${BUILD[WORKSPACE_DIR]}"
echo ""

while true; do
  input_selection "Save and proceed? (y/n/b=back): " "^[ynb]$"
  case $? in
    0)
      case "$SELECTION" in
        y) break ;;
        n) echo "Discarding. Exiting."; exit 0 ;;
        b) LAYER_IDX=3; continue ;;
      esac
      ;;
    1) [[ ! -t 0 ]] && exit 1 ;;
    2) exit 0 ;;
  esac
done

# Save workspace.env
if [[ $DRY_RUN -eq 1 ]]; then
  echo -e "${CYAN}[DRY-RUN] save builds/${BUILD_NAME}/workspace.env${NC}"
else
  save_build "$BUILD_NAME"
fi

# ============================================================================
# Launch Claude
# ============================================================================

echo ""
while true; do
  input_selection "Launch Claude now? (y/n): " "^[yn]$"
  case $? in
    0)
      case "$SELECTION" in
        y) break ;;
        n) echo "Done. Run: cd ${BUILD[WORKSPACE_DIR]} && claude --dangerously-skip-permissions"; exit 0 ;;
      esac
      ;;
    1|2) exit 0 ;;
  esac
done

WORKSPACE="${BUILD[WORKSPACE_DIR]}"
if [[ $DRY_RUN -eq 1 ]]; then
  echo -e "${CYAN}[DRY-RUN] cd ${WORKSPACE} && claude --dangerously-skip-permissions${NC}"
else
  echo -e "${GREEN}Starting Claude in: ${WORKSPACE}${NC}"
  cd "$WORKSPACE"
  exec claude --dangerously-skip-permissions
fi
