#!/bin/bash
# UserPromptSubmit hook: warn when context grows large.
# Reads transcript_path from stdin JSON, scans last assistant
# usage block for cache_read_input_tokens, injects warning to
# stdout when threshold crossed. Stdout becomes additional
# context the model sees on this turn.

set -e

THRESHOLD_WARN=${CONTEXT_WARN_THRESHOLD:-250000}
THRESHOLD_HARD=${CONTEXT_HARD_THRESHOLD:-400000}

input=$(cat)
transcript=$(printf '%s' "$input" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("transcript_path",""))' 2>/dev/null || true)

[ -z "$transcript" ] && exit 0
[ ! -r "$transcript" ] && exit 0

read -r tokens < <(python3 - "$transcript" <<'PY'
import json, sys
path = sys.argv[1]
last = 0
try:
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("message")
            if not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if isinstance(u, dict):
                t = u.get("cache_read_input_tokens", 0) or 0
                if t > last:
                    last = t
except FileNotFoundError:
    pass
print(last)
PY
) || tokens=0

tokens=${tokens:-0}

if [ "$tokens" -ge "$THRESHOLD_HARD" ]; then
  cat <<EOF
CONTEXT CRITICAL: cache_read = ${tokens} tokens (>= ${THRESHOLD_HARD}). Run \`/compact\` BEFORE doing any further work this turn. Do not start new tool calls until compacted.
EOF
elif [ "$tokens" -ge "$THRESHOLD_WARN" ]; then
  cat <<EOF
CONTEXT WARNING: cache_read = ${tokens} tokens (>= ${THRESHOLD_WARN}). At next natural phase boundary (task done, commit landed) call \`/compact\`. Long contexts increase API hang risk.
EOF
fi

exit 0
