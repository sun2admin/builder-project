#!/bin/bash
# /manage-rec-plugins — edit recommended-plugins.json (the recommended L3 plugin set).
# Per SPQ1-12 in .claude/plans/manage-rec-plugins.md.

set -euo pipefail

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
CYAN=$'\033[0;36m'
YELLOW=$'\033[0;33m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
NC=$'\033[0m'

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"
REC_FILE="$REPO_ROOT/tools/build-stack/build_stack/data/recommended-plugins.json"
SELECTOR_LIB="$REPO_ROOT/.claude/skills/_lib/plugin-selector.sh"

read_input() { printf '%s' "$1" >&2; read -r INPUT; }
err()  { echo -e "${RED}✘ $1${NC}" >&2; }
ok()   { echo -e "${GREEN}✓ $1${NC}" >&2; }
info() { echo -e "${CYAN}$1${NC}" >&2; }
warn() { echo -e "${YELLOW}⚠ $1${NC}" >&2; }
dim()  { echo -e "${DIM}$1${NC}" >&2; }

ensure_file() {
  if [[ ! -f "$REC_FILE" ]]; then
    mkdir -p "$(dirname "$REC_FILE")"
    cat > "$REC_FILE" <<EOF
{
  "schema_version": 1,
  "_comment": "Recommended plugins baked into recommended L3 image. Edit via /manage-rec-plugins.",
  "plugins": []
}
EOF
    info "created empty recommended-plugins.json"
  fi
}

view_recommended() {
  local count
  count=$(jq '.plugins | length' "$REC_FILE")
  echo >&2
  echo -e "${BOLD}Recommended plugins ($count)${NC}" >&2
  echo >&2
  if [[ "$count" -eq 0 ]]; then
    dim "  (none)"
    return
  fi
  local i=0
  while IFS=$'\t' read -r mkt plugin cat added; do
    i=$((i+1))
    local cat_label="${cat:-uncategorized}"
    [[ "$cat_label" == "null" ]] && cat_label="uncategorized"
    echo -e "  $i) $plugin ${DIM}($mkt, $cat_label)${NC}" >&2
    dim "       added: $added"
  done < <(jq -r '.plugins[] | [.marketplace, .plugin, (.category // "null"), (.added_at // "")] | @tsv' "$REC_FILE")
}

remove_recommended() {
  local count
  count=$(jq '.plugins | length' "$REC_FILE")
  if [[ "$count" -eq 0 ]]; then
    err "nothing to remove"
    return
  fi
  view_recommended
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
  target=$(jq -r --argjson i "$idx" '.plugins[$i] | "\(.marketplace) :: \(.plugin)"' "$REC_FILE")
  echo >&2
  read_input "Confirm removal of $target? [y/N]: "
  if [[ ! "$INPUT" =~ ^[yY]$ ]]; then
    info "cancelled"
    return
  fi
  local tmp
  tmp=$(mktemp)
  jq --argjson i "$idx" 'del(.plugins[$i])' "$REC_FILE" > "$tmp" && mv "$tmp" "$REC_FILE"
  ok "removed $target"
  warn "recommended L3 image rebuild required (via /deploy-stack) for change to take effect"
}

add_recommended() {
  if [[ ! -f "$SELECTOR_LIB" ]]; then
    err "selector lib not found: $SELECTOR_LIB"
    return
  fi

  # shellcheck disable=SC1090
  source "$SELECTOR_LIB"

  local tmp_out
  tmp_out=$(mktemp)
  trap 'rm -f "$tmp_out"' RETURN

  if ! plugin_selector_run --mode rec-plugins --exclude-recommended --out "$tmp_out"; then
    info "no plugins added"
    return
  fi

  local added
  added=$(jq 'length' "$tmp_out")
  if [[ "$added" -eq 0 ]]; then
    info "no plugins added"
    return
  fi

  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local merged
  merged=$(mktemp)
  jq --slurpfile new "$tmp_out" --arg t "$now" '
    .plugins as $existing
    | $new[0] | map({marketplace, plugin, category, added_at: $t}) as $new_entries
    | $new_entries | reduce .[] as $n ($existing;
        if any(.[]; .marketplace == $n.marketplace and .plugin == $n.plugin) then .
        else . + [$n] end)
    | . as $combined
    | { schema_version: 1, _comment: "Recommended plugins baked into recommended L3 image. Edit via /manage-rec-plugins.", plugins: $combined }
  ' "$REC_FILE" > "$merged" && mv "$merged" "$REC_FILE"

  ok "merged $added plugin(s) into recommended set"
  warn "recommended L3 image rebuild required (via /deploy-stack) for change to take effect"
}

main_menu() {
  while true; do
    echo >&2
    echo -e "${BOLD}/manage-rec-plugins${NC}" >&2
    echo >&2
    echo "  v) view current recommended plugins" >&2
    echo "  a) add more plugins (selector flow)" >&2
    echo "  r) remove a recommended plugin" >&2
    echo "  q) quit" >&2
    echo >&2
    read_input "Choice: "
    case "$INPUT" in
      v|V) view_recommended ;;
      a|A) add_recommended ;;
      r|R) remove_recommended ;;
      q|Q) info "bye"; return 0 ;;
      *)   err "invalid choice: $INPUT" ;;
    esac
  done
}

ensure_file
main_menu
