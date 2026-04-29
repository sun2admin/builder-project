---
name: new-plugin-layer skill needs repo verification
description: Skill must verify GitHub repo/image existence before offering prebuilt, not assume
type: feedback
originSessionId: 0ff12816-d740-4e1d-bfd5-4f53f2a05a1d
---
**Issue:** Step 7a currently assumes that if a prebuilt is defined in plugin-lists.json, the corresponding GitHub repo and Docker image exist. This is not always true.

**Why:** When we created "build-repo-plugins" prebuilt, it was added to standards.json with a repo name (claude-plugins-build-repo), but the actual GitHub repo hasn't been created yet.

**How to apply:** Before Step 7a offers to use an existing image, the skill must verify the repo actually exists:
```bash
gh api repos/sun2admin/claude-plugins-build-repo 2>/dev/null
```

If the repo does NOT exist, proceed to Step 8 (hash check and deduplication) to create it. Only skip to Step 9 if the repo verification succeeds.

This prevents offering non-existent images and ensures all referenced repos are actually created.