#!/bin/bash
# Layer 4: Project search, selection, GHCR validation, clone, workspace init
# Usage: build-layer4.sh <ai_install> [current_project_selected]
# stdout: WORKSPACE_DIR path
# exit 0=done, 1=quit, 2=back

source "$(dirname "$0")/../build-workspace/lib.sh"

AI_INSTALL="${1:-claude}"
CURRENT="${2:-}"
GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null)

echo -e "\n${BLUE}=== Layer 4: Project ===${NC}" >&2
echo "Searching GitHub for ${AI_INSTALL}-prj repos..." >&2

PROJECTS=$(gh search repos "topic:${AI_INSTALL}-prj user:${GITHUB_USER}" \
  --json nameWithOwner,description,pushedAt \
  --jq '.[] | "\(.nameWithOwner) (\(.pushedAt[0:10])): \(.description // "no description")"' \
  2>/dev/null || echo "")

echo "" >&2

# No projects found
if [[ -z "$PROJECTS" ]]; then
  echo -e "${YELLOW}No projects found with ${AI_INSTALL}-prj tag.${NC}" >&2
  echo "" >&2
  echo "  c) continue without project" >&2
  echo "  b) back" >&2
  echo "  q) quit" >&2
  echo "" >&2
  while true; do
    input_selection "Selection: " "^[cb]$"
    case $? in
      0) case "$SELECTION" in
           c) echo "/workspace/${AI_INSTALL}"; exit 0 ;;
           b) exit 2 ;;
         esac ;;
      1) [[ ! -t 0 ]] && exit 1 ;;
      2) exit 1 ;;
    esac
  done
fi

# Display project list
mapfile -t PROJ_LINES <<< "$PROJECTS"
count=${#PROJ_LINES[@]}

for i in "${!PROJ_LINES[@]}"; do
  num=$((i + 1))
  repo=$(echo "${PROJ_LINES[$i]}" | cut -d' ' -f1)
  short="${repo##*/}"
  if [[ "$repo" == "$CURRENT" && -n "$CURRENT" ]]; then
    echo -e "  $num) ${GREEN}${PROJ_LINES[$i]} (current)${NC}" >&2
  else
    echo "  $num) ${PROJ_LINES[$i]}" >&2
  fi
done
echo "  n) none — no project" >&2
echo "  b) back" >&2
echo "  q) quit" >&2
echo "" >&2

while true; do
  input_selection "Selection: " "^[0-9]+$|^[nb]$"
  case $? in
    0)
      case "$SELECTION" in
        n) echo "/workspace/${AI_INSTALL}"; exit 0 ;;
        b) exit 2 ;;
        [0-9]*)
          if [[ $SELECTION -ge 1 && $SELECTION -le $count ]]; then
            PROJECT_REPO=$(echo "${PROJ_LINES[$((SELECTION - 1))]}" | cut -d' ' -f1)
            validate_and_clone "$PROJECT_REPO"
            exit $?
          else
            echo -e "${RED}Invalid selection.${NC}" >&2
          fi
          ;;
      esac
      ;;
    1) [[ ! -t 0 ]] && exit 1 ;;
    2) exit 1 ;;
  esac
done

validate_and_clone() {
  local repo="$1"
  local name="${repo##*/}"
  local ghcr_image="ghcr.io/${GITHUB_USER}/${name}:latest"

  echo "" >&2
  echo "Validating GHCR image: ${ghcr_image}..." >&2

  if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] docker manifest inspect ${ghcr_image}${NC}" >&2
    echo -e "${GREEN}✓ Image exists (mocked)${NC}" >&2
  elif ! docker manifest inspect "$ghcr_image" &>/dev/null; then
    echo -e "${YELLOW}Image not found in GHCR.${NC}" >&2
    echo "  y) trigger build via: gh workflow run build -R $repo" >&2
    echo "  s) skip — continue without this project" >&2
    echo "  q) quit" >&2
    echo "" >&2
    while true; do
      input_selection "Selection: " "^[ysq]$"
      case $? in
        0) case "$SELECTION" in
             y)
               echo -e "${BLUE}Triggering build...${NC}" >&2
               gh workflow run build -R "$repo" >&2 || true
               read -r -p "Press enter when build completes, or ctrl+c to cancel: " >&2
               ;;
             s) echo "/workspace/${AI_INSTALL}"; return 0 ;;
             q) return 1 ;;
           esac ;;
        1) [[ ! -t 0 ]] && return 1 ;;
        2) return 1 ;;
      esac
    done
  else
    echo -e "${GREEN}✓ Image exists in GHCR${NC}" >&2
  fi

  # Clone
  local workspace="/workspace/${AI_INSTALL}/${name}"
  echo "Cloning to: ${workspace}..." >&2

  if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] git clone https://github.com/${repo}.git ${workspace}${NC}" >&2
  else
    mkdir -p "/workspace/${AI_INSTALL}"
    if ! git clone "https://github.com/${repo}.git" "${workspace}" >&2; then
      echo -e "${RED}✘ Clone failed${NC}" >&2
      return 1
    fi

    # Validate structure
    if [[ ! -d "${workspace}/.git" || ! -d "${workspace}/.claude" ]]; then
      echo -e "${RED}✘ Project missing .git or .claude directory${NC}" >&2
      return 1
    fi

    # Seed memory
    if [[ -f "${workspace}/.devcontainer/scripts/init-workspace.sh" ]]; then
      bash "${workspace}/.devcontainer/scripts/init-workspace.sh" >&2 || true
    else
      local canonical
      canonical=$(echo "$workspace" | sed 's|^/||;s|/|-|g')
      mkdir -p "${HOME}/.claude/projects/${canonical}/memory"
    fi

    create_sync_skill "${workspace}"
  fi

  echo -e "${GREEN}✓ Project ready${NC}" >&2
  echo "${workspace}"
  return 0
}

create_sync_skill() {
  local workspace="$1"
  local sync_dir="${workspace}/.claude/commands/sync-workspace-repo"
  mkdir -p "$sync_dir"
  cat > "${sync_dir}/SKILL.md" << 'EOF'
---
name: sync-workspace-repo
description: Sync workspace memory back to git repository. Use after long sessions to persist Claude memory.
shortcut: sync
---

# /sync-workspace-repo

Copies memory files from `~/.claude/projects/<cwd>/memory/` back to the repository, commits, and pushes to origin main.
EOF
  echo -e "${GREEN}✓ Created sync skill${NC}" >&2
}
