---
name: Check existing mounts before creating directories
description: Always check for existing mounted directories (like /home/claude/data) before creating new ones in the workspace
type: feedback
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
When outputting files or data, check for existing mounts first using `mount | grep -i data` or `ls -la /home/claude/data` before creating new directories.

**Why:** The devcontainer may have host mounts (like `/home/claude/data` → host `/Users`) that are the intended location for persistent output. Creating parallel directories in `/workspace/` instead loses the data or puts it in the wrong location.

**How to apply:** Before creating any output directory, check: `mount` or `ls -la /home/claude/` to see what's already mounted. Use existing mounts for persistent data.
