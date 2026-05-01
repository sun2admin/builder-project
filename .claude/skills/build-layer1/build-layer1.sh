#!/bin/bash
# Layer 1: Base image selection
# Usage: build-layer1.sh [current_value]
# stdout: selected BASE_IMAGE
# exit 0=selected, 1=quit, 2=back

source "$(dirname "$0")/../build-workspace/lib.sh"

CURRENT="${1:-}"
readonly BASES=("" "light" "latest" "playwright_with_chromium" "playwright_with_firefox" "playwright_with_webkit" "playwright_with_all")

echo -e "\n${BLUE}=== Layer 1: Base Image ===${NC}" >&2
echo "" >&2

for i in 1 2 3 4 5 6; do
  label="${BASES[$i]}"
  if [[ "$label" == "$CURRENT" && -n "$CURRENT" ]]; then
    echo -e "  $i) ${GREEN}${label} (current)${NC}" >&2
  else
    echo "  $i) $label" >&2
  fi
done
echo "  b) back" >&2
echo "  q) quit" >&2
echo "" >&2

while true; do
  input_selection "Selection: " "^[1-6b]$"
  case $? in
    0)
      case "$SELECTION" in
        [1-6])
          echo "${BASES[$SELECTION]}"
          exit 0
          ;;
        b) exit 2 ;;
      esac
      ;;
    1)
      [[ ! -t 0 ]] && exit 1
      ;;
    2) exit 1 ;;
  esac
done
