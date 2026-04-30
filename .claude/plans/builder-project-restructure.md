# Plan: builder-project Directory Restructure

## Goal
Slim the root CLAUDE.md so it is an overview only — per-layer detail lives in each
layer's own nested CLAUDE.md. The nested CLAUDE.md approach is already in place.

---

## Approach: Nested CLAUDE.md per Layer (already implemented)

Each layer subdirectory has its own `CLAUDE.md` with layer-specific detail:

| Layer | Nested CLAUDE.md |
|---|---|
| Layer 1 | `layer1-ai-depends/CLAUDE.md` |
| Layer 2 | `layer2-ai-install/CLAUDE.md` |
| Layer 3 | `plugins/CLAUDE.md` |
| Layer 4 Part 1 | `layer4-part1/CLAUDE.md` |

The root `CLAUDE.md` should contain only:
- Project purpose (1–2 sentences)
- 4-layer architecture diagram + dependency chain
- Layer disambiguation rules (always ask before proceeding; declare "I am working on Layer X")
- Plan-building rules
- Cross-cutting rules: GHCR always private, bash not zsh, credentials to ~/.profile

---

## Step 1: Slim Root CLAUDE.md

**Keep** (~25 lines total):
- Project purpose sentence + pointer to nested CLAUDE.md files
- Architecture table
- Dependency cascade note
- Layer 4 Part 2 explanation
- Working Across Layers section
- Plan Building section
- Cross-Cutting Rules section

**Remove**:
- Any layer-specific detail that duplicates what is in a nested CLAUDE.md

---

## Status
- [x] SessionStart hook added (session-start.sh + settings.json)
- [x] Nested CLAUDE.md files already in place for all layers
- [ ] Root CLAUDE.md not yet slimmed
- [ ] Ready to implement
