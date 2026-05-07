#!/bin/bash
# Auto-sync project memory. Invoked from PreCompact, Stop, SessionEnd hooks.
# Layered design:
#   PreCompact  → always sync (compaction is the highest fidelity-loss moment)
#   Stop        → sync only if N or more memory files changed since last sync
#   SessionEnd  → always sync (best-effort exit handoff)
#
# Reads hook stdin to swallow it (Claude Code hooks always send JSON), but does
# not require any field. Event name is passed as $1 from the settings entry.

set -u

EVENT="${1:-unknown}"
THRESHOLD="${MEMORY_SYNC_THRESHOLD:-3}"
PROJECT="${CLAUDE_PROJECT_DIR:-/workspace/claude/builder-project}"
MARKER="$PROJECT/.claude/.last-memory-sync"
SYNC_BIN="$PROJECT/.claude/skills/sync-prj-repos-memory/sync-prj-repos-memory.sh"
LOG="$PROJECT/.claude/.last-memory-sync.log"

# Discard stdin so the upstream hook process doesn't block on a full pipe.
cat >/dev/null 2>&1 || true

[ ! -x "$SYNC_BIN" ] && exit 0

# Resolve the live memory dir from the project root via the same canonicalize
# rule the sync script uses (slashes → dashes, trailing slash stripped).
canonical=$(echo "${PROJECT%/}" | sed 's|/|-|g')
live_memory="$HOME/.claude/projects/$canonical/memory"

count_changed() {
  [ ! -d "$live_memory" ] && { echo 0; return; }
  if [ -f "$MARKER" ]; then
    find "$live_memory" -maxdepth 1 -name '*.md' -newer "$MARKER" -type f 2>/dev/null | wc -l | tr -d ' '
  else
    find "$live_memory" -maxdepth 1 -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' '
  fi
}

run_sync() {
  local reason="$1"
  {
    echo "=== $(date -Iseconds) event=$EVENT reason=$reason ==="
    bash "$SYNC_BIN" "$PROJECT" 2>&1
    rc=$?
    echo "=== exit=$rc ==="
    [ $rc -eq 0 ] && touch "$MARKER"
  } >>"$LOG" 2>&1
}

case "$EVENT" in
  PreCompact)
    run_sync "compact-imminent"
    ;;
  Stop)
    n=$(count_changed)
    if [ "$n" -ge "$THRESHOLD" ]; then
      run_sync "threshold n=$n>=$THRESHOLD"
    fi
    ;;
  SessionEnd)
    run_sync "session-end"
    ;;
  *)
    exit 0
    ;;
esac

exit 0
