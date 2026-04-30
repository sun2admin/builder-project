---
name: /build-project Skill - Clarifications and Decisions
description: Key decisions made about /build-project skill implementation, answers to clarifying questions, and patterns to follow
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Clarifying Questions - Answered

**Q1: Base image and layer2-ai-install variants - how to fetch?**
- A: Search dynamically on every skill execution (not static list)
- Implementation: Query GitHub repos for available tags

**Q2: GHCR image validation - how to verify image exists?**
- A: Use the most basic method to verify a build exists
- Implementation: Likely `docker pull --dry-run` or `docker manifest inspect` against GHCR
- Do not over-engineer validation

**Q3: init-claude-prj.sh - does it exist?**
- A: No, it does not currently exist
- Status: New script to create
- Replaces: Current init-memory.sh pattern
- Purpose: Seed memory from git to ~/.claude/projects/<path>/memory/

**Q4: sync-project-repo skill - does it exist?**
- A: No, sync-* skills do not exist yet
- Status: Create template when needed
- Pattern: Similar to update-build-with-claude (copy memory back to repo, commit)

**Q5: When no project is selected - what to do?**
- A: Just exit; don't create any config files
- Behavior: sync-project-repo skill only created if project is selected
- Result: User leaves with empty /workspace, can set up manually

## Open Questions for Next Phase

These questions should be revisited during implementation:

1. Plugin layer display (step 1a):
 - Show which plugins are included in each layer, or just name/description?

2. Clone strategy (step 4):
 - Should use shallow clone, specific depth, or full clone?
 - Any special git clone flags?

3. Sync skill behavior:
 - Should sync-project-repo auto-commit like update-build-with-claude?
 - Or just copy files and let user commit?

4. Error handling:
 - On git clone failure, invalid repos, etc. - error out or retry/fallback?

5. Script execution order (step 4):
 - Run init-claude-prj.sh before or after setting cwd?
 - Does init-claude-prj.sh require cwd to be set?

6. Project validation:
 - Verify cloned project has valid .claude/ directory structure?
 - Or trust user's project is well-formed?

7. Claude startup (step 5):
 - Just run `claude` command, or pass specific flags?
 - Any environment variables to set?

## Implementation Patterns to Follow

- **init-claude-prj.sh**: Modeled after init-memory.sh (seed from git, use cp -n to preserve live)
- **sync-project-repo**: Modeled after update-build-with-claude (copy, commit, push)
- **Error messages**: Clear and actionable for user
- **Dynamic queries**: Always fetch fresh data (variants, repos, images) per skill execution