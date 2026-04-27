---
name: Always default to plugins first
description: When a task has a relevant plugin available, use it as the primary approach before considering alternatives
type: feedback
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
When executing a task, check available plugins first and default to using them if relevant. Don't reach for workarounds (raw Python, direct libraries) unless no suitable plugin exists.

**Why:** Plugins are pre-baked into images specifically so Claude will use them as the primary tool. Skipping them means:
- Not testing if they work
- Not leveraging the architecture as designed
- Wasting the value of pre-installation and seeding

**How to apply:** Task arrives → Check available plugins (via `claude plugin list` or context awareness) → If relevant plugin exists, use it → Fall back to alternatives only if plugin unavailable or unsuitable.