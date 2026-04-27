# update-build-with-claude

Update the build-with-claude repo with any changes made during the current session, ensuring memory, skills, and config are committed and will be available on next container start.

## What this skill does

1. Syncs live memory files back to the repo
2. Stages and commits all changes in build-with-claude
3. Pushes to origin

## Usage

```
/update-build-with-claude
```

## Steps

### 1. Sync memory files
- [ ] Copy ALL files from live memory to repo (overwrite, not just newer):
  - `cp ~/.claude/projects/workspace-claude/memory/*.md /workspace/claude/.claude/memory/`
- [ ] Identify and remove stale files from repo that don't exist in live:
  - For each file in `/workspace/claude/.claude/memory/`, check if it exists in `~/.claude/projects/workspace-claude/memory/`
  - Delete any repo files that have no corresponding live file
- [ ] Verify file counts match: `ls -1 ~/.claude/projects/workspace-claude/memory/*.md | wc -l` should equal `ls -1 /workspace/claude/.claude/memory/*.md | wc -l`

### 2. Review all changes
- [ ] Run `git status` to identify all modified, deleted, and untracked files
- [ ] Run `git diff` to review substantive changes before staging
- [ ] Verify settings.local.json is NOT being committed

### 3. Commit and push
- [ ] Stage all memory files and MEMORY.md index: `git add .claude/memory/`
- [ ] Unstage settings.local.json if accidentally added: `git restore --staged .claude/settings.local.json`
- [ ] Commit with a descriptive message (include list of new/updated/deleted files)
- [ ] Push to origin main: `git push origin main`
- [ ] Confirm push succeeded

## Notes

- **Complete sync, not incremental**: Copy ALL files from live to repo (overwriting existing)
  - This ensures updated memory fixes are propagated, not skipped
  - This ensures stale files are removed, not preserved
- **Seed behavior** (container startup): Uses `cp -n` (no-overwrite) from repo to live, preserving live changes
- **Never commit**: `.claude/settings.local.json`, secrets, credential files, unrelated scripts
- **Memory persistence**: After sync, memory is authoritative in the repo and will seed all future container starts
