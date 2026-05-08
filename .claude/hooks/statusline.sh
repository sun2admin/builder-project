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

tokens=0
if [ -n "$transcript" ] && [ -r "$transcript" ]; then
  tokens=$(python3 - "$transcript" <<'PY' 2>/dev/null || echo 0
import json, sys
# Track MOST RECENT assistant usage entry, not max — see context-warn.sh
# for the same fix. /compact's own summarization API call records the full
# pre-compact context as one entry; a max-tracker would lock that as the
# watermark and never recover after the conversation actually shrinks.
last=0
try:
    with open(sys.argv[1]) as f:
        for line in f:
            try: d=json.loads(line)
            except: continue
            m=d.get("message")
            if isinstance(m,dict):
                u=m.get("usage")
                if isinstance(u,dict):
                    last=(u.get("cache_read_input_tokens",0) or 0)+(u.get("cache_creation_input_tokens",0) or 0)+(u.get("input_tokens",0) or 0)
except FileNotFoundError: pass
print(last)
PY
)
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
