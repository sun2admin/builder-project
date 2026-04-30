---
name: /build-project Skill - Clarifications and Decisions
description: Key decisions made about /build-project skill implementation, answers to clarifying questions, and patterns to follow
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## Clarifying Questions - Answered

**Q1: Base image and layer2-ai-install variants - how to fetch?**
- A: Search dynamically on every skill execution (not static list)
- Implementation: Query GitHub repos for available tags

**Q2: GHCR image validation - how to verify image exists?**
- A: Use the most basic method to verify a build exists
- Implementation: `docker manifest inspect` against GHCR
- Do not over-engineer validation

**Q3: load-projects.sh - does it exist?**
- A: Yes, lives in `layer4-devcontainer/scripts/load-projects.sh`
- Purpose: Clones project repos, seeds memory from `.claude/memory/` into named volume

**Q4: sync-prj-repos-memory skill - does it exist?**
- A: Yes, already implemented as `/sync-prj-repos-memory`
- Pattern: Copies memory from named volume back to git repo, commits, pushes

**Q5: When no project is selected - what to do?**
- A: Just exit; don't create any config files

## Open Questions for Next Phase

1. Plugin layer display: show plugin list or just name/description?
2. Clone strategy: shallow clone, specific depth, or full?
3. Sync skill behavior: auto-commit or let user commit?
4. Error handling: on git clone failure, error out or retry?
5. Project validation: verify cloned project has valid .claude/ structure?
6. Claude startup: just `claude` command, or pass specific flags?

## Implementation Patterns to Follow

- **Memory seeding**: `cp -n` from `.claude/memory/` → `~/.claude/projects/<path>/memory/` (load-projects.sh pattern)
- **Memory sync**: copy back to git, commit, push (sync-prj-repos-memory pattern)
- **Error messages**: clear and actionable
- **Dynamic queries**: always fetch fresh data (layer variants, repos, images) per execution
