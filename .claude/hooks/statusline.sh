#!/bin/bash
# Combined statusline: caveman badge + context meter.
# Stdin: JSON from Claude Code (session_id, transcript_path, model, ...).
# Stdout: single line shown below prompt.

set -u

input=$(cat)

caveman=$(printf '%s' "$input" | bash /opt/claude-custom-plugins/marketplaces/caveman/hooks/caveman-statusline.sh 2>/dev/null || true)

transcript=$(printf '%s' "$input" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("transcript_path",""))
except: print("")' 2>/dev/null)

WARN=${CONTEXT_WARN_THRESHOLD:-250000}
HARD=${CONTEXT_HARD_THRESHOLD:-400000}
WINDOW=${CONTEXT_WINDOW:-300000}

# Token extraction shared with context-warn.sh — see lib/tokens.py.
# Helper prints "cache_read cache_creation input_tokens"; statusline shows
# the sum (most honest "cost of next turn" reading).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tokens=0
if [ -n "$transcript" ] && [ -r "$transcript" ]; then
  read -r cr cc it < <(python3 "$SCRIPT_DIR/lib/tokens.py" "$transcript" 2>/dev/null) || true
  tokens=$(( ${cr:-0} + ${cc:-0} + ${it:-0} ))
fi

human() {
  local n=$1
  if   [ "$n" -ge 1000000 ]; then printf '%.1fM' "$(echo "$n/1000000" | bc -l)"
  elif [ "$n" -ge 1000 ];    then printf '%dK' "$((n/1000))"
  else printf '%d' "$n"
  fi
}

pct=$(( tokens * 100 / (WINDOW>0?WINDOW:1) ))

if   [ "$tokens" -ge "$HARD" ]; then color='\033[1;31m'   # bold red
elif [ "$tokens" -ge "$WARN" ]; then color='\033[38;5;208m' # orange
else                                color='\033[38;5;244m' # gray
fi
reset='\033[0m'

ctx=$(printf '%bctx %s/%s (%d%%)%b' "$color" "$(human "$tokens")" "$(human "$WINDOW")" "$pct" "$reset")

if [ -n "$caveman" ]; then
  printf '%s  %s\n' "$caveman" "$ctx"
else
  printf '%s\n' "$ctx"
fi
