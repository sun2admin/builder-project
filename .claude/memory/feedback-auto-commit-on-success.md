---
name: Auto-commit successful changes to repo
description: Commit changes to the repo immediately after making them if no errors occurred
type: feedback
originSessionId: 00b94795-bbde-41ce-bbb7-690083573b18
---
Whenever you make changes to the codebase and no errors occur, commit those changes immediately. Do not ask for permission or wait for approval before committing — just do it.

**Why:** Keeps the repo state current and avoids accumulating uncommitted changes. Reduces manual overhead of managing git state.

**How to apply:** After any successful code change (tests pass, no errors, feature/fix works), run:
```bash
git add <files>
git commit -m "<message>"
git push
```

Only skip commits if:
- Errors occurred during implementation
- Tests failed
- The work is incomplete/blocked
- Explicitly told not to commit

