#!/bin/bash
# Shared library for build-workspace skill suite
# Source with: source "$(dirname "$0")/../build-workspace/lib.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Set by input_selection on valid input
SELECTION=""

# Execute or print (dry-run). Reads $DRY_RUN env var.
run_cmd() {
  if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] $*${NC}" >&2
  else
    eval "$@"
  fi
}

# Read one line of input in TTY or piped mode.
# Sets global $input. Writes prompt to stderr.
read_input() {
  local prompt="$1"
  if [[ -t 0 ]]; then
    read -r -p "$prompt" input
  else
    printf '%s' "$prompt" >&2
    IFS= read -r input
  fi
}

# Prompt for a menu selection and validate it.
# Sets global $SELECTION on success.
# Returns: 0=valid, 1=invalid/EOF, 2=quit
input_selection() {
  local prompt="$1"
  local valid_regex="$2"

  if ! read_input "$prompt"; then
    return 1  # EOF
  fi

  if [[ "$input" == "q" ]]; then
    return 2  # quit
  fi

  if [[ "$input" =~ $valid_regex ]]; then
    SELECTION="$input"
    return 0
  fi

  echo -e "${RED}Invalid selection. Try again.${NC}" >&2
  return 1
}
