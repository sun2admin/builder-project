#!/bin/bash
# Shared library for build-stack skill (self-contained).
# Adapted from the deleted build-workspace skill's lib.sh.

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SELECTION=""

run_cmd() {
  if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
    echo -e "${CYAN}[DRY-RUN] $*${NC}" >&2
  else
    eval "$@"
  fi
}

read_input() {
  local prompt="$1"
  if [[ -t 0 ]]; then
    read -r -p "$prompt" input
  else
    printf '%s' "$prompt" >&2
    IFS= read -r input
  fi
}

# Returns: 0=valid, 1=invalid/EOF, 2=quit
input_selection() {
  local prompt="$1"
  local valid_regex="$2"

  if ! read_input "$prompt"; then
    return 1
  fi

  if [[ "$input" == "q" ]]; then
    return 2
  fi

  if [[ "$input" =~ $valid_regex ]]; then
    SELECTION="$input"
    return 0
  fi

  echo -e "${RED}Invalid selection. Try again.${NC}" >&2
  return 1
}
