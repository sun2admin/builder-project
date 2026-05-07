---
name: New GitHub repos default private
description: All new GitHub repositories must be created private unless user explicitly specifies otherwise
type: feedback
originSessionId: aef50037-641d-4235-b110-e932ad6e21c2
---
All new GitHub repos default to **private** unless user explicitly says public. Use `gh repo create <owner>/<name> --private` (never plain `gh repo create`).

**Why:** User established this 2026-05-07 alongside Layer 4 TTY fix work, when creating `sun2admin/build-stack-with-claude`. Aligns with existing CLAUDE.md cross-cutting rule that all GHCR images are private — same posture extended to source repos. Default-private prevents accidental exposure of work-in-progress, credential references, internal infra naming.

**How to apply:** Any time a new GitHub repo is created (via `gh repo create`, MCP `mcp__github__create_repository`, or web flow scripted), pass private flag / set visibility=private. If user says "create a public repo" or "make it public" explicitly → override. Otherwise default private and confirm before creation if visibility ambiguous.

**Cross-reference:** CLAUDE.md cross-cutting rules section (added same date).
