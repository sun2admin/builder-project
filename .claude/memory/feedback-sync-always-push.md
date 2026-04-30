---
name: sync-prj-repos-memory always push
description: The sync skill must always run git push as its final step, even when there is nothing new to commit
type: feedback
originSessionId: cb7f1bbb-113d-4d4c-bb9b-448456603aaa
---
Always run `git push` at the end of `/sync-prj-repos-memory`, even if `git status` is clean and there was nothing new to commit.

**Why:** Sessions routinely produce commits via direct git commands (e.g. during plan execution) that are never pushed. The sync skill is the canonical push point. Stopping at "nothing to commit" leaves unpushed commits silently stranded on the local branch.

**How to apply:** After the memory copy + `git add -A` + optional commit step, always run `git push origin main` unconditionally as the final action.
