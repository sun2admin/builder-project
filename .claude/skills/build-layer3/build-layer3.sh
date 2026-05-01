#!/bin/bash
# Layer 3: Plugin layer discovery and selection
# Usage: build-layer3.sh <ai_install> [current_plugin_layer]
# stdout: selected PLUGIN_LAYER short name or "none"
# exit 0=selected, 1=quit, 2=back

source "$(dirname "$0")/../build-workspace/lib.sh"

AI_INSTALL="${1:-claude}"
CURRENT="${2:-}"
GITHUB_USER=$(gh api user --jq '.login' 2>/dev/null)

echo -e "\n${BLUE}=== Layer 3: Plugin Layer ===${NC}" >&2

# Gemini plugins not yet available
if [[ "$AI_INSTALL" == "gemini" ]]; then
  echo -e "${YELLOW}Gemini plugins coming soon. Proceeding with no plugin layer.${NC}" >&2
  echo "" >&2
  echo "  c) continue without plugins" >&2
  echo "  b) back" >&2
  echo "  q) quit" >&2
  echo "" >&2
  while true; do
    input_selection "Selection: " "^[cb]$"
    case $? in
      0) case "$SELECTION" in
           c) echo "none"; exit 0 ;;
           b) exit 2 ;;
         esac ;;
      1) [[ ! -t 0 ]] && exit 1 ;;
      2) exit 1 ;;
    esac
  done
fi

# Discover claude plugin layers
echo "Searching GitHub for plugin layers..." >&2
PLUGIN_REPOS=$(gh repo list "$GITHUB_USER" \
  --json nameWithOwner,repositoryTopics \
  --jq '.[] | select((.nameWithOwner | test("claude-plugins-")) and (.repositoryTopics | map(.name) | index("anthropic-plugins"))) | .nameWithOwner' \
  2>/dev/null || echo "")

echo "" >&2

if [[ -z "$PLUGIN_REPOS" ]]; then
  echo -e "${YELLOW}No plugin layers found.${NC}" >&2
  echo "" >&2
  echo "  c) continue without plugins" >&2
  echo "  b) back" >&2
  echo "  q) quit" >&2
  echo "" >&2
  while true; do
    input_selection "Selection: " "^[cb]$"
    case $? in
      0) case "$SELECTION" in
           c) echo "none"; exit 0 ;;
           b) exit 2 ;;
         esac ;;
      1) [[ ! -t 0 ]] && exit 1 ;;
      2) exit 1 ;;
    esac
  done
fi

# Display plugin menu
mapfile -t REPOS <<< "$PLUGIN_REPOS"
count=${#REPOS[@]}

for i in "${!REPOS[@]}"; do
  num=$((i + 1))
  short="${REPOS[$i]##*/}"
  if [[ "$short" == "$CURRENT" && -n "$CURRENT" ]]; then
    echo -e "  $num) ${GREEN}${short} (current)${NC}" >&2
  else
    echo "  $num) $short" >&2
  fi
done
echo "  b) back" >&2
echo "  q) quit" >&2
echo "" >&2

while true; do
  input_selection "Selection: " "^[0-9]+$|^[b]$"
  case $? in
    0)
      case "$SELECTION" in
        b) exit 2 ;;
        [0-9]*)
          if [[ $SELECTION -ge 1 && $SELECTION -le $count ]]; then
            echo "${REPOS[$((SELECTION - 1))]##*/}"
            exit 0
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
