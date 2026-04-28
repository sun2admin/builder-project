#!/bin/bash
set -e

# /build-workspace skill implementation
# Scaffolds a new Claude or Gemini workspace with all dependencies
# Architecture: State machine with explicit state transitions

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes for UI
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# State Machine Variables
# ============================================================================
declare -g CURRENT_STATE="INIT"
declare -g DRY_RUN=0
declare -g BASE_IMAGE=""
declare -g AI_INSTALL=""
declare -g PLUGIN_LAYER=""
declare -g PROJECT_SELECTED=""
declare -g PROJECT_REPO=""
declare -g WORKSPACE_DIR=""
declare -g PLUGIN_REPOS=""
declare -g PROJECTS=""
declare -g GITHUB_USER=""  # Dynamically detected from authenticated user

# ============================================================================
# Dry-run command executor
# ============================================================================
run_cmd() {
  local cmd="$@"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] $cmd${NC}"
    return 0
  else
    eval "$cmd"
  fi
}

# ============================================================================
# Unified Input Handler - Supports both interactive and piped input
# ============================================================================
read_input() {
  local prompt="$1"

  # Check if stdin is a TTY (interactive) or piped
  if [[ -t 0 ]]; then
    # Interactive mode: use read -p (user can type anytime)
    read -p "$prompt" input
    return 0
  else
    # Piped mode: print prompt then read one line at a time
    printf '%s' "$prompt" >&2
    if IFS= read -r input; then
      return 0
    else
      return 1  # EOF
    fi
  fi
}

# Safe selection input with validation
# Returns: 0 = valid choice, 1 = EOF or invalid input in piped mode, 2 = quit requested
input_selection() {
  local prompt="$1"
  local valid_regex="$2"
  local input

  if ! read_input "$prompt"; then
    return 1  # EOF
  fi

  # Check for quit
  if [[ "$input" == "q" ]]; then
    return 2  # Quit requested
  fi

  # Validate against regex
  if [[ "$input" =~ $valid_regex ]]; then
    echo "$input"
    return 0
  fi

  # Invalid input
  if [[ -t 0 ]]; then
    # Interactive mode: show error and loop (handled by caller)
    echo -e "${RED}Invalid selection. Please try again.${NC}"
    return 1
  else
    # Piped mode: fail fast
    echo -e "${RED}Invalid input: $input${NC}" >&2
    return 1
  fi
}

# ============================================================================
# STATE: INIT - Initialize and parse arguments
# ============================================================================
state_init() {
  if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=1
    echo -e "${YELLOW}[DRY-RUN MODE]${NC} No actual changes will be made"
    echo ""
  fi

  # Detect authenticated GitHub user
  GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null)
  if [[ -z "$GITHUB_USER" ]]; then
    echo -e "${RED}✘ Error: Not authenticated with GitHub${NC}"
    echo "Please run: gh auth login"
    CURRENT_STATE="DONE"
    return 1
  fi

  echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║        /build-workspace - New Development Workspace        ║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
  echo ""

  CURRENT_STATE="BASE_IMAGE"
  return 0
}

# ============================================================================
# STATE: BASE_IMAGE - Select base image variant
# ============================================================================
state_base_image() {
  echo -e "${BLUE}=== Layer 1: Select Base Image ===${NC}"
  echo ""
  echo "1) light                        — Minimal (Python, git, curl)"
  echo "2) latest                       — Default (light + dev tools + graphics)"
  echo "3) playwright_with_chromium     — latest + Playwright Chromium"
  echo "4) playwright_with_firefox      — latest + Playwright Firefox"
  echo "5) playwright_with_webkit       — latest + Playwright WebKit"
  echo "6) playwright_with_all          — latest + all Playwright browsers"
  echo "q) quit"
  echo ""

  local result
  result=$(input_selection "Selection: " "^[1-6q]$")
  local exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    case $exit_code in
      1) # EOF or invalid in piped mode
        if [[ ! -t 0 ]]; then
          echo -e "${RED}Invalid input or EOF. Exiting.${NC}" >&2
        fi
        CURRENT_STATE="DONE"
        return 1
        ;;
      2) # Quit requested
        CURRENT_STATE="DONE"
        return 0
        ;;
    esac
  fi

  if [[ "$result" == "q" ]]; then
    CURRENT_STATE="DONE"
    return 0
  fi

  # Map selection to base image
  local bases=("" "light" "latest" "playwright_with_chromium" \
               "playwright_with_firefox" "playwright_with_webkit" "playwright_with_all")
  BASE_IMAGE="${bases[$result]}"

  echo -e "${GREEN}✓ Selected base image: ${BASE_IMAGE}${NC}"
  echo ""

  CURRENT_STATE="AI_SELECTION"
  return 0
}

# ============================================================================
# STATE: AI_SELECTION - Select AI CLI
# ============================================================================
state_ai_selection() {
  echo -e "${BLUE}=== Layer 2: Select AI CLI ===${NC}"
  echo ""
  echo "1) claude  — Claude Code CLI"
  echo "2) gemini  — Gemini Code CLI"
  echo "b) back"
  echo "q) quit"
  echo ""

  local result
  result=$(input_selection "Selection: " "^[12bq]$")
  local exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    case $exit_code in
      1) # EOF or invalid
        if [[ ! -t 0 ]]; then
          echo -e "${RED}Invalid input or EOF. Exiting.${NC}" >&2
        fi
        CURRENT_STATE="DONE"
        return 1
        ;;
      2) # Quit requested
        CURRENT_STATE="DONE"
        return 0
        ;;
    esac
  fi

  case "$result" in
    1) AI_INSTALL="claude"; CURRENT_STATE="PLUGIN_FETCH" ;;
    2) AI_INSTALL="gemini"; CURRENT_STATE="PLUGIN_FETCH" ;;
    b) CURRENT_STATE="BASE_IMAGE" ;;
    q) CURRENT_STATE="DONE" ;;
  esac

  if [[ -n "$AI_INSTALL" ]]; then
    echo -e "${GREEN}✓ Selected AI CLI: ${AI_INSTALL}${NC}"
    echo ""
  fi

  return 0
}

# ============================================================================
# STATE: PLUGIN_FETCH - Fetch available plugin layers from GitHub
# ============================================================================
state_plugin_fetch() {
  echo -e "${BLUE}=== Layer 3: Discover Plugin Layer ===${NC}"

  if [[ "$AI_INSTALL" == "claude" ]]; then
    echo "Searching GitHub for plugin layers with anthropic-plugins topic..."

    # Always query GitHub (dry-run only affects destructive operations)
    # Search for repos matching: claude-plugins-* with anthropic-plugins topic
    PLUGIN_REPOS=$(gh repo list "$GITHUB_USER" --json nameWithOwner,repositoryTopics \
      --jq '.[] | select((.nameWithOwner | contains("claude-plugins-")) and (.repositoryTopics | map(.name) | index("anthropic-plugins"))) | .nameWithOwner' 2>/dev/null || echo "")

    if [[ -z "$PLUGIN_REPOS" ]]; then
      echo -e "${YELLOW}⚠ No plugin layers found. Using empty plugin layer.${NC}"
      PLUGIN_LAYER="none"
    fi

  else
    echo -e "${YELLOW}Gemini plugins coming soon${NC}"
    echo "Using empty plugin layer for now."
    PLUGIN_LAYER="none"
  fi

  echo ""
  CURRENT_STATE="PLUGIN_SELECTION"
  return 0
}

# ============================================================================
# STATE: PLUGIN_SELECTION - Select a plugin layer
# ============================================================================
state_plugin_selection() {
  if [[ -z "$PLUGIN_REPOS" ]]; then
    echo -e "${BLUE}=== Layer 3: Plugin Layer ===${NC}"
    echo -e "${YELLOW}No plugin layers available for this AI type${NC}"
    echo "Proceeding with empty plugin layer"
    echo ""
    echo "c) continue"
    echo "b) back"
    echo "q) quit"
    echo ""

    local result
    while true; do
      result=$(input_selection "Selection: " "^[cbq]$")
      local exit_code=$?

      if [[ $exit_code -ne 0 ]]; then
        case $exit_code in
          1) # Invalid input or EOF
            if [[ ! -t 0 ]]; then
              echo -e "${RED}Invalid input. Exiting.${NC}" >&2
              CURRENT_STATE="DONE"
              return 1
            fi
            continue
            ;;
          2) # Quit requested
            CURRENT_STATE="DONE"
            return 0
            ;;
        esac
      fi

      case "$result" in
        c)
          PLUGIN_LAYER="none"
          CURRENT_STATE="PROJECT_SEARCH"
          return 0
          ;;
        b)
          CURRENT_STATE="AI_SELECTION"
          return 0
          ;;
        q)
          CURRENT_STATE="DONE"
          return 0
          ;;
      esac
    done
  fi

  echo -e "${BLUE}=== Layer 3: Select Plugin Layer ===${NC}"
  echo ""
  local count=$(echo "$PLUGIN_REPOS" | wc -l)

  # Display menu
  echo "$PLUGIN_REPOS" | nl -nln -w1 -s') '
  echo "d) details"
  echo "b) back"
  echo "q) quit"
  echo ""

  local result
  while true; do
    result=$(input_selection "Selection: " "^[0-9]+$|^[dbq]$")
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
      case $exit_code in
        1) # Invalid input or EOF
          if [[ ! -t 0 ]]; then
            echo -e "${RED}Invalid input. Exiting.${NC}" >&2
            CURRENT_STATE="DONE"
            return 1
          fi
          # Interactive mode: loop to retry
          continue
          ;;
        2) # Quit requested
          CURRENT_STATE="DONE"
          return 0
          ;;
      esac
    fi

    case "$result" in
      d)
        # Show plugin details
        echo ""
        echo "Plugin Layer Descriptions:"
        echo "  a7f3d2e8: build-repo-plugins (base + skills for repo creation)"
        echo "  3f889e47: base-plus-general-skills (base + general utility plugins)"
        echo "  34e199d2: base-ext-skills (base + external integration plugins)"
        echo ""
        continue
        ;;
      b)
        CURRENT_STATE="AI_SELECTION"
        return 0
        ;;
      q)
        CURRENT_STATE="DONE"
        return 0
        ;;
      [0-9]*)
        if [[ $result -ge 1 && $result -le $count ]]; then
          PLUGIN_LAYER=$(echo "$PLUGIN_REPOS" | sed -n "${result}p" | cut -d'/' -f2)
          echo -e "${GREEN}✓ Selected plugin layer: ${PLUGIN_LAYER}${NC}"
          echo ""
          CURRENT_STATE="PROJECT_SEARCH"
          return 0
        else
          echo -e "${RED}Invalid selection${NC}"
        fi
        ;;
    esac
  done
}

# ============================================================================
# STATE: PROJECT_SEARCH - Search for projects on GitHub
# ============================================================================
state_project_search() {
  echo -e "${BLUE}=== Layer 4: Discover Projects ===${NC}"
  echo "Searching GitHub for ${AI_INSTALL}-prj tagged repos..."

  # Always query GitHub (dry-run only affects destructive operations)
  # Search for repos tagged with: <ai-type>-prj (e.g., claude-prj, gemini-prj)
  PROJECTS=$(gh search repos "topic:${AI_INSTALL}-prj user:${GITHUB_USER}" \
    --json nameWithOwner,description,pushedAt \
    --jq '.[] | "\(.nameWithOwner) (\(.pushedAt[0:10])): \(.description)"' 2>/dev/null || echo "")

  if [[ -z "$PROJECTS" ]]; then
    echo -e "${YELLOW}No projects found with ${AI_INSTALL}-prj tag${NC}"
    PROJECT_SELECTED=""
  fi

  echo ""
  CURRENT_STATE="PROJECT_SELECTION"
  return 0
}

# ============================================================================
# STATE: PROJECT_SELECTION - Select or skip project
# ============================================================================
state_project_selection() {
  if [[ -z "$PROJECTS" ]]; then
    echo -e "${BLUE}=== Layer 4: No Projects Found ===${NC}"
    echo "No projects available with ${AI_INSTALL}-prj tag."
    echo ""
    echo "y) continue without project"
    echo "n) search again"
    echo "b) back"
    echo "q) quit"
    echo ""

    local result
    if ! result=$(input_selection "Selection: " "^[ynbq]$"); then
      case $? in
        1) CURRENT_STATE="DONE"; return 1 ;;
        2) CURRENT_STATE="DONE"; return 0 ;;
      esac
    fi

    case "$result" in
      y) PROJECT_SELECTED=""; CURRENT_STATE="CLONE_INITIALIZE"; return 0 ;;
      n) CURRENT_STATE="PROJECT_SEARCH"; return 0 ;;
      b) CURRENT_STATE="PLUGIN_SELECTION"; return 0 ;;
      q) CURRENT_STATE="DONE"; return 0 ;;
    esac
  fi

  echo -e "${BLUE}=== Layer 4: Select Project ===${NC}"
  echo ""
  local count=$(echo "$PROJECTS" | wc -l)

  # Display menu
  echo "$PROJECTS" | nl -nln -w1 -s') '
  echo "n) none"
  echo "b) back"
  echo "q) quit"
  echo ""

  local result
  while true; do
    result=$(input_selection "Selection: " "^[0-9]+$|^[nbq]$")
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
      case $exit_code in
        1) # Invalid input or EOF
          if [[ ! -t 0 ]]; then
            # Piped mode with invalid input: exit
            CURRENT_STATE="DONE"
            return 1
          fi
          # Interactive mode: loop to retry
          continue
          ;;
        2) # Quit requested
          CURRENT_STATE="DONE"
          return 0
          ;;
      esac
    fi

    case "$result" in
      n)
        PROJECT_SELECTED=""
        echo -e "${YELLOW}Continuing without project${NC}"
        echo ""
        CURRENT_STATE="CLONE_INITIALIZE"
        return 0
        ;;
      b)
        CURRENT_STATE="PLUGIN_SELECTION"
        return 0
        ;;
      q)
        CURRENT_STATE="DONE"
        return 0
        ;;
      [0-9]*)
        if [[ $result -ge 1 && $result -le $count ]]; then
          # Extract repo name from selection
          PROJECT_REPO=$(echo "$PROJECTS" | sed -n "${result}p" | cut -d' ' -f1)

          echo ""
          echo -e "${BLUE}Selected: $PROJECT_REPO${NC}"
          echo "Project details:"
          echo "$PROJECTS" | sed -n "${result}p"
          echo ""

          # Validate GHCR image
          validate_ghcr_image "$PROJECT_REPO"
          return 0
        else
          echo -e "${RED}Invalid selection${NC}"
        fi
        ;;
    esac
  done
}

# ============================================================================
# Helper: Validate GHCR Image Exists
# ============================================================================
validate_ghcr_image() {
  local repo=$1
  local image_name="${repo##*/}"
  local ghcr_image="ghcr.io/sun2admin/${image_name}:latest"

  echo "Validating GHCR image: ${ghcr_image}"

  if [[ $DRY_RUN -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] docker manifest inspect $ghcr_image${NC}"
    echo -e "${GREEN}✓ Image exists in GHCR (mocked)${NC}"
    PROJECT_SELECTED="$PROJECT_REPO"
    echo ""
    CURRENT_STATE="CLONE_INITIALIZE"
    return 0
  fi

  # Try to pull the manifest (dry-run)
  if docker manifest inspect "$ghcr_image" &>/dev/null; then
    echo -e "${GREEN}✓ Image exists in GHCR${NC}"
    PROJECT_SELECTED="$PROJECT_REPO"
    echo ""
    CURRENT_STATE="CLONE_INITIALIZE"
    return 0
  else
    echo -e "${YELLOW}⚠ Image not found in GHCR${NC}"
    local proceed
    if ! proceed=$(input_selection "Build it? (y/n): " "^[yn]$"); then
      CURRENT_STATE="DONE"
      return 1
    fi

    if [[ "$proceed" == "y" ]]; then
      echo -e "${BLUE}Build command: gh workflow run build -R $repo${NC}"
      read -p "Press enter after build completes, or ctrl+c to cancel"
      PROJECT_SELECTED="$PROJECT_REPO"
      echo ""
      CURRENT_STATE="CLONE_INITIALIZE"
    else
      echo -e "${YELLOW}Skipping this project${NC}"
      echo ""
      CURRENT_STATE="PROJECT_SELECTION"
    fi
  fi
}

# ============================================================================
# STATE: CLONE_INITIALIZE - Clone repo and initialize workspace
# ============================================================================
state_clone_initialize() {
  if [[ -z "$PROJECT_SELECTED" ]]; then
    echo -e "${BLUE}=== Layer 5: Initialize Workspace ===${NC}"
    WORKSPACE_DIR="/workspace"
    echo "Using workspace: $WORKSPACE_DIR"
    echo ""

    CURRENT_STATE="SUMMARY_CONFIRM"
    return 0
  fi

  echo -e "${BLUE}=== Layer 5: Clone and Initialize Project ===${NC}"

  local project_name="${PROJECT_SELECTED##*/}"
  WORKSPACE_DIR="/workspace/${AI_INSTALL}/${project_name}"

  echo "Cloning to: $WORKSPACE_DIR"

  if [[ $DRY_RUN -eq 1 ]]; then
    run_cmd "mkdir -p '/workspace/${AI_INSTALL}'"
    run_cmd "git clone 'https://github.com/${PROJECT_SELECTED}.git' '$WORKSPACE_DIR'"
    echo -e "${GREEN}✓ Project cloned and validated (mocked)${NC}"
  else
    mkdir -p "/workspace/${AI_INSTALL}"

    if ! git clone "https://github.com/${PROJECT_SELECTED}.git" "$WORKSPACE_DIR"; then
      echo -e "${RED}✘ Failed to clone repository${NC}"
      CURRENT_STATE="DONE"
      return 1
    fi

    # Run init-workspace.sh before setting cwd
    if [[ -f "$WORKSPACE_DIR/.devcontainer/scripts/init-workspace.sh" ]]; then
      if ! bash "$WORKSPACE_DIR/.devcontainer/scripts/init-workspace.sh"; then
        echo -e "${YELLOW}⚠ init-workspace.sh failed${NC}"
      fi
    else
      # If script doesn't exist, create basic memory seeding
      local canonical_path=$(echo "$WORKSPACE_DIR" | sed 's|^/||;s|/|-|g')
      mkdir -p ~/.claude/projects/$canonical_path/memory
      echo -e "${YELLOW}init-workspace.sh not found, created basic memory dir${NC}"
    fi

    # Verify project structure
    if [[ ! -d "$WORKSPACE_DIR/.claude" ]]; then
      echo -e "${RED}✘ Project missing .claude directory${NC}"
      CURRENT_STATE="DONE"
      return 1
    fi

    if [[ ! -d "$WORKSPACE_DIR/.git" ]]; then
      echo -e "${RED}✘ Project missing .git directory${NC}"
      CURRENT_STATE="DONE"
      return 1
    fi

    echo -e "${GREEN}✓ Project cloned and validated${NC}"
  fi

  echo ""

  # Create sync skill
  create_sync_skill "$WORKSPACE_DIR"

  CURRENT_STATE="SUMMARY_CONFIRM"
  return 0
}

# ============================================================================
# Helper: Create sync skill in cloned project
# ============================================================================
create_sync_skill() {
  local workspace=$1
  local sync_dir="$workspace/.claude/commands/sync-workspace-repo"

  mkdir -p "$sync_dir"

  cat > "$sync_dir/SKILL.md" << 'EOF'
---
name: sync-workspace-repo
description: Sync workspace memory back to git repository
shortcut: sync
usage: |
  /sync-workspace-repo

  Copies memory files from ~/.claude/projects/<cwd>/memory/ back to the
  repository, commits, and pushes to origin.
---

# /sync-workspace-repo

Manually sync workspace memory back to git.

## What it does

1. Copies memory files from live to repo (overwriting)
2. Removes stale files
3. Commits with descriptive message
4. Pushes to origin main

## Usage

```
/sync-workspace-repo
```

This is useful after long development sessions to ensure memory is
persisted and shared with the team.
EOF

  echo -e "${GREEN}✓ Created sync skill${NC}"
}

# ============================================================================
# STATE: SUMMARY_CONFIRM - Show summary and confirm
# ============================================================================
state_summary_confirm() {
  echo -e "${BLUE}=== Layer 6: Configuration Summary ===${NC}"
  echo "Base Image:      ${BASE_IMAGE}"
  echo "AI Install:      ${AI_INSTALL}"
  echo "Plugin Layer:    ${PLUGIN_LAYER}"
  echo "Project:         ${PROJECT_SELECTED:-"(none - using /workspace)"}"
  echo "Workspace:       ${WORKSPACE_DIR}"
  echo ""

  local result
  while true; do
    result=$(input_selection "Proceed with this configuration? (y/n, b for back, q to quit): " "^[ynbq]$")
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
      case $exit_code in
        1) # Invalid input or EOF
          if [[ ! -t 0 ]]; then
            echo -e "${RED}Invalid input. Exiting.${NC}" >&2
            CURRENT_STATE="DONE"
            return 1
          fi
          # Interactive mode: loop to retry
          continue
          ;;
        2) # Quit requested
          CURRENT_STATE="DONE"
          return 0
          ;;
      esac
    fi

    case "$result" in
      y) CURRENT_STATE="EXECUTE"; return 0 ;;
      n) CURRENT_STATE="DONE"; return 0 ;;
      b) CURRENT_STATE="PROJECT_SELECTION"; return 0 ;;
      q) CURRENT_STATE="DONE"; return 0 ;;
    esac
  done
}

# ============================================================================
# STATE: EXECUTE - Start Claude with configuration
# ============================================================================
state_execute() {
  echo ""
  echo -e "${BLUE}=== Layer 7: Start Claude ===${NC}"
  echo "Working directory: $WORKSPACE_DIR"
  echo ""

  if [[ $DRY_RUN -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] cd $WORKSPACE_DIR${NC}"
    echo -e "${CYAN}[DRY-RUN] claude --dangerously-skip-permissions${NC}"
    echo ""
    echo -e "${GREEN}✓ Dry-run complete. Menu flow validated.${NC}"
    echo "To run for real, invoke: /build-workspace"
  else
    cd "$WORKSPACE_DIR"
    echo -e "${GREEN}Starting Claude with flags: --dangerously-skip-permissions${NC}"
    echo ""
    claude --dangerously-skip-permissions
  fi

  CURRENT_STATE="DONE"
  return 0
}

# ============================================================================
# State Machine Dispatcher
# ============================================================================
dispatch_state() {
  case "$CURRENT_STATE" in
    INIT)                 state_init "$@" ;;
    BASE_IMAGE)           state_base_image ;;
    AI_SELECTION)         state_ai_selection ;;
    PLUGIN_FETCH)         state_plugin_fetch ;;
    PLUGIN_SELECTION)     state_plugin_selection ;;
    PROJECT_SEARCH)       state_project_search ;;
    PROJECT_SELECTION)    state_project_selection ;;
    CLONE_INITIALIZE)     state_clone_initialize ;;
    SUMMARY_CONFIRM)      state_summary_confirm ;;
    EXECUTE)              state_execute ;;
    DONE)                 return 0 ;;
    *)                    echo -e "${RED}Unknown state: $CURRENT_STATE${NC}"; exit 1 ;;
  esac
}

# ============================================================================
# Main - State Machine Loop
# ============================================================================
main() {
  while [[ "$CURRENT_STATE" != "DONE" ]]; do
    dispatch_state "$@" || break
  done
}

main "$@"
