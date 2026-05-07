---
name: Compact at phase boundaries; obey context-warn hook
description: Discipline rule for proactively running /compact to avoid long-context API hangs that froze a 25-task build session
type: feedback
originSessionId: 48401218-ea0e-4f4c-b287-4ac9d3d30c67
---
At natural phase boundaries (numbered task complete, commit landed, plan section done) call `/compact`. Hard rule: if cache_read crosses 250K, compact at next boundary; if it crosses 400K, compact immediately before any further work this turn.

The project has a `UserPromptSubmit` hook at `.claude/hooks/context-warn.sh` that injects a `CONTEXT WARNING` (>=250K) or `CONTEXT CRITICAL` (>=400K) line into the turn. When that line appears, it is a directive — call `/compact`, do not ignore.

**Why:** May 7 2026 session 15df376d froze mid-task 25 with 312K cache_read at last assistant turn (peak 578K earlier). API request after user prompt never returned a single token. Long-context first-token latency made a transient network/server stall fatal. Lost work was a single-line image-name revert plus committing.

**How to apply:**
- Treat phase boundaries as the right time to compact, not after they pass.
- Push bulk reads (corpus scans, parity runs, large jsonl analysis) into Agent subagents — their context dies with them, main thread eats only the summary.
- Cap inline tool output: `head -200`, `jq` filters, Read with offset+limit. Never `cat` a multi-MB JSON or jsonl into the conversation.
- If you ever see the hook's `CONTEXT CRITICAL` line, the next assistant turn must be `/compact` — no other tool calls until compacted.
- Memory-only guidance is insufficient (passive); the hook is the active half. Both must be in place.
