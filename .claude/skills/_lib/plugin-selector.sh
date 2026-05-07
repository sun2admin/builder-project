#!/bin/bash
# plugin-selector.sh — shared selector flow for /manage-rec-plugins and /build-stack.
#
# State machine (per .claude/plans/manage-rec-plugins.md SPQ1-12):
#   S1 marketplace menu -> S2 fetch -> S3 category multi-select -> S4 drill-down -> S6 final review
#
# Public API (call these after sourcing this file):
#   plugin_selector_run [--mode rec-plugins|build-stack] [--exclude-recommended] [--out FILE]
#       Returns 0 on confirmed selection, 1 on cancel. Writes JSON array to FILE if given.
#
# Selection JSON shape:
#   [{"marketplace":"owner/repo","plugin":"plugin-name","category":"<cat or null>"}, ...]
#
# State variables (namespaced PS_*):
#   PS_REPO_ROOT, PS_MARKETPLACES_JSON, PS_RECOMMENDED_JSON, PS_CACHE_DIR
#   PS_MODE, PS_EXCLUDE_RECOMMENDED, PS_OUT
#   PS_SELECTIONS (array of "owner/repo|plugin|category")
#   PS_MKT (current marketplace owner/repo), PS_MKT_FILE (cached marketplace.json path)
#   PS_CATS (array of selected categories), PS_CAT_INDEX (S4 cycle index)

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "plugin-selector.sh must be sourced, not executed" >&2
  exit 1
fi

# ─── Color codes ───────────────────────────────────────────────────────────────
PS_RED=$'\033[0;31m'
PS_GREEN=$'\033[0;32m'
PS_CYAN=$'\033[0;36m'
PS_YELLOW=$'\033[0;33m'
PS_DIM=$'\033[2m'
PS_BOLD=$'\033[1m'
PS_NC=$'\033[0m'

# ─── Helpers ───────────────────────────────────────────────────────────────────
_ps_read() { printf '%s' "$1" >&2; read -r _ps_input; }
_ps_err()  { echo -e "${PS_RED}✘ $1${PS_NC}" >&2; }
_ps_ok()   { echo -e "${PS_GREEN}✓ $1${PS_NC}" >&2; }
_ps_info() { echo -e "${PS_CYAN}$1${PS_NC}" >&2; }
_ps_dim()  { echo -e "${PS_DIM}$1${PS_NC}" >&2; }

_ps_in_array() {
  local needle="$1"; shift
  local h
  for h in "$@"; do [[ "$h" == "$needle" ]] && return 0; done
  return 1
}

# Match a recommended plugin entry (owner/repo|plugin format).
_ps_is_recommended() {
  [[ -z "${PS_RECOMMENDED_JSON:-}" || ! -f "$PS_RECOMMENDED_JSON" ]] && return 1
  local key="$1"  # owner/repo|plugin
  local mkt="${key%%|*}"
  local plugin="${key##*|}"
  jq -e --arg m "$mkt" --arg p "$plugin" \
    '.plugins[] | select(.marketplace == $m and .plugin == $p)' \
    "$PS_RECOMMENDED_JSON" > /dev/null 2>&1
}

# ─── Init ──────────────────────────────────────────────────────────────────────
plugin_selector_run() {
  PS_MODE="rec-plugins"
  PS_EXCLUDE_RECOMMENDED=0
  PS_OUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode) PS_MODE="$2"; shift 2 ;;
      --exclude-recommended) PS_EXCLUDE_RECOMMENDED=1; shift ;;
      --out)  PS_OUT="$2"; shift 2 ;;
      *) _ps_err "unknown plugin_selector_run flag: $1"; return 2 ;;
    esac
  done

  if [[ -z "${PS_REPO_ROOT:-}" ]]; then
    PS_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  fi
  PS_MARKETPLACES_JSON="${PS_MARKETPLACES_JSON:-$PS_REPO_ROOT/tools/build-stack/build_stack/data/marketplaces.json}"
  PS_RECOMMENDED_JSON="${PS_RECOMMENDED_JSON:-$PS_REPO_ROOT/tools/build-stack/build_stack/data/recommended-plugins.json}"
  PS_CACHE_DIR="${PS_CACHE_DIR:-$PS_REPO_ROOT/analyzed_repos/marketplaces}"
  mkdir -p "$PS_CACHE_DIR"

  if [[ ! -f "$PS_MARKETPLACES_JSON" ]]; then
    _ps_err "marketplaces.json not found: $PS_MARKETPLACES_JSON"
    _ps_info "Run /manage-known-marketplaces to add at least one marketplace."
    return 2
  fi

  PS_SELECTIONS=()
  local state="S1"
  while [[ "$state" != "DONE" && "$state" != "CANCEL" ]]; do
    case "$state" in
      S1) state="$(_ps_state_s1)" ;;
      S2) state="$(_ps_state_s2)" ;;
      S3) state="$(_ps_state_s3)" ;;
      S4) state="$(_ps_state_s4)" ;;
      S6) state="$(_ps_state_s6)" ;;
      *)  _ps_err "invalid state: $state"; return 2 ;;
    esac
  done

  if [[ "$state" == "CANCEL" ]]; then
    _ps_info "selection cancelled"
    return 1
  fi

  if [[ -n "$PS_OUT" ]]; then
    _ps_emit_selections > "$PS_OUT"
  fi
  _ps_ok "${#PS_SELECTIONS[@]} plugin(s) selected"
  return 0
}

_ps_emit_selections() {
  local entries=()
  local s
  for s in "${PS_SELECTIONS[@]}"; do
    local mkt="${s%%|*}"
    local rest="${s#*|}"
    local plugin="${rest%%|*}"
    local cat="${rest##*|}"
    [[ "$cat" == "null" || -z "$cat" ]] && cat="null" || cat="\"$cat\""
    entries+=("{\"marketplace\":\"$mkt\",\"plugin\":\"$plugin\",\"category\":$cat}")
  done
  local IFS=,
  echo "[${entries[*]}]" | jq '.'
}

# ─── S1: Marketplace menu ──────────────────────────────────────────────────────
_ps_state_s1() {
  local count
  count=$(jq '.marketplaces | length' "$PS_MARKETPLACES_JSON")
  if [[ "$count" -eq 0 ]]; then
    _ps_err "no marketplaces registered"
    _ps_info "Run /manage-known-marketplaces to add one."
    echo "CANCEL"; return
  fi

  echo >&2
  echo -e "${PS_BOLD}S1 — Pick marketplace${PS_NC}" >&2
  echo >&2
  local i=0
  while IFS=$'\t' read -r owner repo is_default; do
    i=$((i+1))
    local label="$owner/$repo"
    [[ "$is_default" == "true" ]] && label+=" ${PS_DIM}(default)${PS_NC}"
    if [[ -n "${#PS_SELECTIONS[@]}" && ${#PS_SELECTIONS[@]} -gt 0 ]]; then
      local sel_count=0
      local s
      for s in "${PS_SELECTIONS[@]}"; do
        [[ "${s%%|*}" == "$owner/$repo" ]] && sel_count=$((sel_count+1))
      done
      [[ $sel_count -gt 0 ]] && label+=" ${PS_GREEN}[$sel_count selected]${PS_NC}"
    fi
    echo -e "  $i) $label" >&2
  done < <(jq -r '.marketplaces[] | [.owner, .repo, (.default // false | tostring)] | @tsv' "$PS_MARKETPLACES_JSON")

  echo >&2
  if [[ ${#PS_SELECTIONS[@]} -gt 0 ]]; then
    echo "  f) finished — proceed to final review (${#PS_SELECTIONS[@]} selected)" >&2
  fi
  echo "  q) quit / cancel" >&2
  echo >&2
  _ps_read "Choice: "
  local choice="$_ps_input"

  case "$choice" in
    q|Q) echo "CANCEL"; return ;;
    f|F)
      [[ ${#PS_SELECTIONS[@]} -eq 0 ]] && { _ps_err "no plugins selected yet"; echo "S1"; return; }
      echo "S6"; return ;;
    *)
      if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 && "$choice" -le "$count" ]]; then
        local idx=$((choice-1))
        PS_MKT="$(jq -r --argjson i "$idx" '.marketplaces[$i] | "\(.owner)/\(.repo)"' "$PS_MARKETPLACES_JSON")"
        echo "S2"; return
      fi
      _ps_err "invalid choice: $choice"
      echo "S1"; return ;;
  esac
}

# ─── S2: Fetch marketplace ─────────────────────────────────────────────────────
_ps_state_s2() {
  local owner="${PS_MKT%%/*}"
  local repo="${PS_MKT##*/}"
  local cache_dir="$PS_CACHE_DIR/$owner/$repo"
  PS_MKT_FILE="$cache_dir/marketplace.json"
  mkdir -p "$cache_dir"

  if [[ ! -f "$PS_MKT_FILE" ]]; then
    _ps_info "fetching $PS_MKT marketplace.json..."
    if ! gh api "repos/$PS_MKT/contents/.claude-plugin/marketplace.json" --jq '.content' 2>/dev/null \
         | base64 -d > "$PS_MKT_FILE.tmp" 2>/dev/null; then
      rm -f "$PS_MKT_FILE.tmp"
      _ps_err "failed to fetch $PS_MKT marketplace.json"
      _ps_info "check network + that repo exists and contains .claude-plugin/marketplace.json"
      echo "S1"; return
    fi
    if ! jq -e '.plugins' "$PS_MKT_FILE.tmp" > /dev/null 2>&1; then
      rm -f "$PS_MKT_FILE.tmp"
      _ps_err "$PS_MKT marketplace.json invalid (no .plugins array)"
      echo "S1"; return
    fi
    mv "$PS_MKT_FILE.tmp" "$PS_MKT_FILE"
    _ps_ok "cached $(jq '.plugins | length' "$PS_MKT_FILE") plugin(s)"
  else
    _ps_dim "using cached $PS_MKT marketplace.json"
  fi

  PS_CATS=()
  PS_CAT_INDEX=0
  echo "S3"
}

# ─── S3: Category multi-select ─────────────────────────────────────────────────
_ps_state_s3() {
  local cats_tsv
  cats_tsv=$(jq -r '
    [.plugins[] | (.category // "uncategorized")]
    | group_by(.) | map({cat: .[0], count: length})
    | sort_by(.cat)
    | .[] | [.cat, (.count|tostring)] | @tsv
  ' "$PS_MKT_FILE")

  local cats=()
  local cat_counts=()
  while IFS=$'\t' read -r c n; do
    cats+=("$c")
    cat_counts+=("$n")
  done <<< "$cats_tsv"

  echo >&2
  echo -e "${PS_BOLD}S3 — Categories in $PS_MKT${PS_NC}" >&2
  _ps_dim "  toggle by number; d=drill-down selected; s=submit-all-in-selected; m=back to main" >&2
  echo >&2
  local i
  for i in "${!cats[@]}"; do
    local mark="[ ]"
    _ps_in_array "${cats[$i]}" "${PS_CATS[@]:-}" && mark="[${PS_GREEN}x${PS_NC}]"
    echo -e "  $((i+1))) $mark ${cats[$i]} ${PS_DIM}(${cat_counts[$i]})${PS_NC}" >&2
  done
  echo >&2
  echo "  d) drill-down into selected categories" >&2
  echo "  s) submit-all-plugins from selected categories" >&2
  echo "  m) back to main menu (S1)" >&2
  echo "  q) quit / cancel" >&2
  echo >&2
  _ps_read "Choice: "
  local choice="$_ps_input"

  case "$choice" in
    q|Q) echo "CANCEL"; return ;;
    m|M) echo "S1"; return ;;
    d|D)
      if [[ ${#PS_CATS[@]} -eq 0 ]]; then _ps_err "select at least 1 category first"; echo "S3"; return; fi
      PS_CAT_INDEX=0
      echo "S4"; return ;;
    s|S)
      if [[ ${#PS_CATS[@]} -eq 0 ]]; then _ps_err "select at least 1 category first"; echo "S3"; return; fi
      _ps_submit_all_in_cats
      echo "S1"; return ;;
    *)
      if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 && "$choice" -le "${#cats[@]}" ]]; then
        local picked="${cats[$((choice-1))]}"
        if _ps_in_array "$picked" "${PS_CATS[@]:-}"; then
          local new=()
          local c
          for c in "${PS_CATS[@]}"; do [[ "$c" != "$picked" ]] && new+=("$c"); done
          PS_CATS=("${new[@]:-}")
          [[ -z "${PS_CATS[0]:-}" ]] && PS_CATS=()
        else
          PS_CATS+=("$picked")
        fi
      else
        _ps_err "invalid choice: $choice"
      fi
      echo "S3"; return ;;
  esac
}

_ps_submit_all_in_cats() {
  local c
  for c in "${PS_CATS[@]}"; do
    local jq_filter
    if [[ "$c" == "uncategorized" ]]; then
      jq_filter='.plugins[] | select(.category == null or .category == "uncategorized") | [.name, (.category // "null")] | @tsv'
    else
      jq_filter=".plugins[] | select(.category == \"$c\") | [.name, (.category // \"null\")] | @tsv"
    fi
    while IFS=$'\t' read -r pname pcat; do
      local key="$PS_MKT|$pname|$pcat"
      _ps_in_array "$key" "${PS_SELECTIONS[@]:-}" || PS_SELECTIONS+=("$key")
    done < <(jq -r "$jq_filter" "$PS_MKT_FILE")
  done
  _ps_ok "added all plugins from ${#PS_CATS[@]} category(ies)"
}

# ─── S4: Drill-down per selected category ──────────────────────────────────────
_ps_state_s4() {
  if [[ "$PS_CAT_INDEX" -ge "${#PS_CATS[@]}" ]]; then
    _ps_ok "drilled-down all selected categories"
    echo "S3"; return
  fi
  local cur_cat="${PS_CATS[$PS_CAT_INDEX]}"

  local jq_filter
  if [[ "$cur_cat" == "uncategorized" ]]; then
    jq_filter='.plugins[] | select(.category == null or .category == "uncategorized") | [.name, (.description // ""), (.category // "null")] | @tsv'
  else
    jq_filter=".plugins[] | select(.category == \"$cur_cat\") | [.name, (.description // \"\"), (.category // \"null\")] | @tsv"
  fi
  local plugin_names=()
  local plugin_descs=()
  local plugin_cats=()
  while IFS=$'\t' read -r pname pdesc pcat; do
    plugin_names+=("$pname")
    plugin_descs+=("$pdesc")
    plugin_cats+=("$pcat")
  done < <(jq -r "$jq_filter" "$PS_MKT_FILE")

  echo >&2
  echo -e "${PS_BOLD}S4 — Plugins in $cur_cat${PS_NC} ${PS_DIM}(category $((PS_CAT_INDEX+1))/${#PS_CATS[@]})${PS_NC}" >&2
  echo >&2
  local i
  for i in "${!plugin_names[@]}"; do
    local pname="${plugin_names[$i]}"
    local key="$PS_MKT|$pname|${plugin_cats[$i]}"
    local mark="[ ]"
    _ps_in_array "$key" "${PS_SELECTIONS[@]:-}" && mark="[${PS_GREEN}x${PS_NC}]"
    local rec_tag=""
    _ps_is_recommended "$PS_MKT|$pname" && rec_tag=" ${PS_YELLOW}[incl. w/ recommended]${PS_NC}"
    if [[ "$PS_EXCLUDE_RECOMMENDED" == "1" ]] && _ps_is_recommended "$PS_MKT|$pname"; then continue; fi
    echo -e "  $((i+1))) $mark $pname$rec_tag" >&2
  done
  echo >&2
  echo "  i <n>) info for plugin n" >&2
  if [[ $((PS_CAT_INDEX+1)) -lt ${#PS_CATS[@]} ]]; then
    echo "  n) next selected category" >&2
  fi
  if [[ "$PS_CAT_INDEX" -gt 0 ]]; then
    echo "  b) back to previous category" >&2
  fi
  echo "  c) return to category menu (S3)" >&2
  echo "  m) return to main menu (S1)" >&2
  echo "  f) finished — proceed to final review" >&2
  echo "  q) quit / cancel" >&2
  echo >&2
  _ps_read "Choice: "
  local choice="$_ps_input"

  case "$choice" in
    q|Q) echo "CANCEL"; return ;;
    m|M) echo "S1"; return ;;
    c|C) echo "S3"; return ;;
    f|F)
      [[ ${#PS_SELECTIONS[@]} -eq 0 ]] && { _ps_err "no plugins selected"; echo "S4"; return; }
      echo "S6"; return ;;
    n|N)
      if [[ $((PS_CAT_INDEX+1)) -lt ${#PS_CATS[@]} ]]; then
        PS_CAT_INDEX=$((PS_CAT_INDEX+1))
      else
        _ps_err "no more categories — use c, m, or f"
      fi
      echo "S4"; return ;;
    b|B)
      if [[ "$PS_CAT_INDEX" -gt 0 ]]; then
        PS_CAT_INDEX=$((PS_CAT_INDEX-1))
      else
        _ps_err "no previous category"
      fi
      echo "S4"; return ;;
    i\ *|I\ *)
      local n="${choice#* }"
      if [[ "$n" =~ ^[0-9]+$ ]] && [[ "$n" -ge 1 && "$n" -le "${#plugin_names[@]}" ]]; then
        _ps_show_plugin_info "${plugin_names[$((n-1))]}"
      else
        _ps_err "invalid plugin index for info: $n"
      fi
      echo "S4"; return ;;
    *)
      if [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 && "$choice" -le "${#plugin_names[@]}" ]]; then
        local pname="${plugin_names[$((choice-1))]}"
        local key="$PS_MKT|$pname|${plugin_cats[$((choice-1))]}"
        if _ps_in_array "$key" "${PS_SELECTIONS[@]:-}"; then
          local new=()
          local s
          for s in "${PS_SELECTIONS[@]}"; do [[ "$s" != "$key" ]] && new+=("$s"); done
          PS_SELECTIONS=("${new[@]:-}")
          [[ -z "${PS_SELECTIONS[0]:-}" ]] && PS_SELECTIONS=()
        else
          PS_SELECTIONS+=("$key")
        fi
      else
        _ps_err "invalid choice: $choice"
      fi
      echo "S4"; return ;;
  esac
}

_ps_show_plugin_info() {
  local pname="$1"
  local info
  info=$(jq -r --arg n "$pname" '
    .plugins[] | select(.name == $n) |
    "  name        : \(.name)
  description : \(.description // "(none)")
  category    : \(.category // "(uncategorized)")
  author      : \(.author.name // .author // "(unknown)")
  source      : \(.source // "(unknown)")
  homepage    : \(.homepage // "(none)")"
  ' "$PS_MKT_FILE")
  echo >&2
  echo -e "${PS_CYAN}─── plugin info ───${PS_NC}" >&2
  echo "$info" >&2
  echo -e "${PS_CYAN}───────────────────${PS_NC}" >&2
}

# ─── S6: Final review ──────────────────────────────────────────────────────────
_ps_state_s6() {
  echo >&2
  echo -e "${PS_BOLD}S6 — Final review (${#PS_SELECTIONS[@]} plugin(s))${PS_NC}" >&2
  echo >&2
  local s
  local i=0
  for s in "${PS_SELECTIONS[@]}"; do
    i=$((i+1))
    local mkt="${s%%|*}"
    local rest="${s#*|}"
    local pname="${rest%%|*}"
    local pcat="${rest##*|}"
    echo -e "  $i) $pname ${PS_DIM}($mkt, $pcat)${PS_NC}" >&2
  done
  echo >&2
  echo "  c) confirm — write selections" >&2
  echo "  e) edit — back to main menu (keeps selections)" >&2
  echo "  x) discard all and start over" >&2
  echo "  q) quit / cancel" >&2
  echo >&2
  _ps_read "Choice: "
  case "$_ps_input" in
    c|C) echo "DONE"; return ;;
    e|E) echo "S1"; return ;;
    x|X) PS_SELECTIONS=(); echo "S1"; return ;;
    q|Q) echo "CANCEL"; return ;;
    *)   _ps_err "invalid choice: $_ps_input"; echo "S6"; return ;;
  esac
}
