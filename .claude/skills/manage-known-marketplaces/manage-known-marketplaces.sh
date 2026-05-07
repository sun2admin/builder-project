#!/bin/bash
# /manage-known-marketplaces — add/list/remove marketplaces.json entries
# Per MKMQ1-6 in .claude/plans/manage-rec-plugins.md.

set -euo pipefail

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
CYAN=$'\033[0;36m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
NC=$'\033[0m'

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
MKT_FILE="$REPO_ROOT/tools/build-stack/build_stack/data/marketplaces.json"

read_input() { printf '%s' "$1" >&2; read -r INPUT; }
err()  { echo -e "${RED}✘ $1${NC}" >&2; }
ok()   { echo -e "${GREEN}✓ $1${NC}" >&2; }
info() { echo -e "${CYAN}$1${NC}" >&2; }
dim()  { echo -e "${DIM}$1${NC}" >&2; }

ensure_file() {
  if [[ ! -f "$MKT_FILE" ]]; then
    mkdir -p "$(dirname "$MKT_FILE")"
    cat > "$MKT_FILE" <<EOF
{
  "schema_version": 1,
  "marketplaces": [
    {
      "owner": "anthropics",
      "repo": "claude-plugins-official",
      "marketplace_name": "claude-plugins-official",
      "added_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "default": true
    }
  ]
}
EOF
    info "seeded marketplaces.json with anthropics/claude-plugins-official (default)"
  fi
}

list_marketplaces() {
  local count
  count=$(jq '.marketplaces | length' "$MKT_FILE")
  echo >&2
  echo -e "${BOLD}Registered marketplaces ($count)${NC}" >&2
  echo >&2
  if [[ "$count" -eq 0 ]]; then
    dim "  (none)"
    return
  fi
  local i=0
  while IFS=$'\t' read -r owner repo name is_default added; do
    i=$((i+1))
    local label="$owner/$repo"
    [[ -n "$name" && "$name" != "null" && "$name" != "$repo" ]] && label+=" ${DIM}($name)${NC}"
    [[ "$is_default" == "true" ]] && label+=" ${GREEN}[default]${NC}"
    echo -e "  $i) $label" >&2
    dim "       added: $added"
  done < <(jq -r '.marketplaces[] | [.owner, .repo, (.marketplace_name // ""), (.default // false | tostring), (.added_at // "")] | @tsv' "$MKT_FILE")
}

validate_repo() {
  local owner_repo="$1"
  if ! gh repo view "$owner_repo" --json name >/dev/null 2>&1; then
    err "repo not found or not accessible: $owner_repo"
    return 1
  fi
  ok "repo exists: $owner_repo"
  if ! gh api "repos/$owner_repo/contents/.claude-plugin/marketplace.json" >/dev/null 2>&1; then
    err "missing .claude-plugin/marketplace.json in $owner_repo"
    return 1
  fi
  ok "marketplace.json present in $owner_repo"
  return 0
}

fetch_marketplace_name() {
  local owner_repo="$1"
  local name
  name=$(gh api "repos/$owner_repo/contents/.claude-plugin/marketplace.json" --jq '.content' 2>/dev/null \
         | base64 -d 2>/dev/null \
         | jq -r '.name // empty' 2>/dev/null)
  echo "${name:-${owner_repo##*/}}"
}

add_marketplace() {
  echo >&2
  read_input "Marketplace owner/repo (e.g. anthropics/claude-plugins-official): "
  local owner_repo="$INPUT"

  if [[ ! "$owner_repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    err "invalid format. Use owner/repo"
    return
  fi

  local owner="${owner_repo%%/*}"
  local repo="${owner_repo##*/}"

  if jq -e --arg o "$owner" --arg r "$repo" '.marketplaces[] | select(.owner == $o and .repo == $r)' "$MKT_FILE" >/dev/null; then
    err "already registered: $owner_repo"
    return
  fi

  validate_repo "$owner_repo" || return
  local mkt_name
  mkt_name=$(fetch_marketplace_name "$owner_repo")
  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  local tmp
  tmp=$(mktemp)
  jq --arg o "$owner" --arg r "$repo" --arg n "$mkt_name" --arg t "$now" \
     '.marketplaces += [{owner: $o, repo: $r, marketplace_name: $n, added_at: $t}]' \
     "$MKT_FILE" > "$tmp" && mv "$tmp" "$MKT_FILE"
  ok "added $owner_repo (marketplace name: $mkt_name)"
}

remove_marketplace() {
  local count
  count=$(jq '.marketplaces | length' "$MKT_FILE")
  if [[ "$count" -eq 0 ]]; then
    err "nothing to remove"
    return
  fi
  list_marketplaces
  echo >&2
  read_input "Number to remove (or 'c' to cancel): "
  local choice="$INPUT"
  if [[ "$choice" =~ ^[cC]$ ]]; then
    info "cancelled"
    return
  fi
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 || "$choice" -gt "$count" ]]; then
    err "invalid number: $choice"
    return
  fi
  local idx=$((choice-1))
  local target
  target=$(jq -r --argjson i "$idx" '.marketplaces[$i] | "\(.owner)/\(.repo)"' "$MKT_FILE")
  echo >&2
  read_input "Confirm removal of $target? [y/N]: "
  if [[ ! "$INPUT" =~ ^[yY]$ ]]; then
    info "cancelled"
    return
  fi
  local tmp
  tmp=$(mktemp)
  jq --argjson i "$idx" 'del(.marketplaces[$i])' "$MKT_FILE" > "$tmp" && mv "$tmp" "$MKT_FILE"
  ok "removed $target"
}

main_menu() {
  while true; do
    echo >&2
    echo -e "${BOLD}/manage-known-marketplaces${NC}" >&2
    echo >&2
    echo "  a) add" >&2
    echo "  l) list" >&2
    echo "  r) remove" >&2
    echo "  q) quit" >&2
    echo >&2
    read_input "Choice: "
    case "$INPUT" in
      a|A) add_marketplace ;;
      l|L) list_marketplaces ;;
      r|R) remove_marketplace ;;
      q|Q) info "bye"; return 0 ;;
      *)   err "invalid choice: $INPUT" ;;
    esac
  done
}

ensure_file
main_menu
