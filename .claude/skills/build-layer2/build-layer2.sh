#!/bin/bash
# Layer 2: AI CLI selection
# Usage: build-layer2.sh [current_value]
# stdout: selected AI_INSTALL (claude|gemini)
# exit 0=selected, 1=quit, 2=back

source "$(dirname "$0")/../build-workspace/lib.sh"

CURRENT="${1:-}"

echo -e "\n${BLUE}=== Layer 2: AI CLI ===${NC}" >&2
echo "" >&2
[[ "$CURRENT" == "claude" ]] && echo -e "  1) ${GREEN}claude (current)${NC}" >&2 || echo "  1) claude" >&2
[[ "$CURRENT" == "gemini" ]] && echo -e "  2) ${GREEN}gemini (current)${NC}" >&2 || echo "  2) gemini" >&2
echo "  b) back" >&2
echo "  q) quit" >&2
echo "" >&2

while true; do
  input_selection "Selection: " "^[12b]$"
  case $? in
    0)
      case "$SELECTION" in
        1) echo "claude"; exit 0 ;;
        2) echo "gemini"; exit 0 ;;
        b) exit 2 ;;
      esac
      ;;
    1) [[ ! -t 0 ]] && exit 1 ;;
    2) exit 1 ;;
  esac
done
