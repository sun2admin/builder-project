# Plan: builder-project Directory Restructure

## Goal
Align builder-project with Anthropic best practices for Claude Code project structure, while correctly reflecting the Layer 4 two-part architecture.

## Current State
- `CLAUDE.md` — mixes architecture overview with Layer 4 Part 1 operational detail
- `.claude/rules/` — exists but empty (`.gitkeep` only)
- No path-scoped or modular rule files
- Layer 4 Part 1 and Part 2 are not distinguished in project documentation

## Proposed Structure

```
builder-project/
├── CLAUDE.md                          # ~20 lines: overview + cross-layer rules only
├── .claude/
│   ├── settings.json                  # hooks + permissions (no layer detail here)
│   ├── hooks/
│   │   └── session-start.sh           # PATH setup via $CLAUDE_PROJECT_DIR (done)
│   ├── rules/
│   │   ├── layer-1-base-ai.md         # base-ai-layer context
│   │   ├── layer-2-ai-install.md      # ai-install-layer context
│   │   ├── layer-3-plugins.md         # plugin layer context
│   │   ├── layer-4-part1.md           # Part 1: container/dependency layer
│   │   ├── layer-4-part2.md           # Part 2: claude project repos pattern
│   │   └── cross-layer.md             # spans all layers (GHCR private, bash, credentials)
│   ├── skills/                        # unchanged
│   ├── commands/                      # unchanged
│   ├── memory/                        # unchanged (git-committed pattern)
│   └── plans/                         # unchanged
└── .mcp.json                          # unchanged for now
```

## Layer 4 Two-Part Distinction

Layer 4 is two distinct roles that must be documented separately:

**Part 1 — Container/Dependency Layer** (`layer-4-part1.md`)
- Repos: `build-with-claude`, `build-with-claude-stage2`, `build-with-claude-stage3`
- Contains: devcontainer.json, init scripts, firewall rules, Layer 3 image reference
- Dictated by what Part 2 needs — if Part 2 uses `gh` or GitHub MCP, Part 1 must provide it
- Detail: `update-github-mcp.yml` pattern, `init-github-mcp.sh`, `postStartCommand` sequencing

**Part 2 — Claude Project Repos** (`layer-4-part2.md`)
- Repos: `builder-project` and all future claude/ai project repos
- Contains: CLAUDE.md, .claude/, .mcp.json, skills, memory — Claude files only
- Self-contained and portable: usable independently of the 4-layer architecture
- Cloned to `/workspace/<ai-name>/<repo-name>` (e.g. `/workspace/claude/builder-project`)
- Only one AI workspace exists at a time (`claude/` or `gemini/`, not both)

## Hook Consideration for layer-4-part2.md

The `SessionStart` hook + `$CLAUDE_ENV_FILE` pattern is a **standard for all Part 2 repos**:
- Adds `$CLAUDE_PROJECT_DIR/scripts/bin` to PATH dynamically at session start
- Enables project-local binaries (gh, MCP server, etc.) without Part 1 involvement
- Implemented in: `.claude/hooks/session-start.sh` + `settings.json` SessionStart hook
- `layer-4-part2.md` must document this as a required pattern when a Part 2 repo uses local binaries

Cross-reference: see `mcp-binary-to-part2.md` for the full gh libs / MCP binary migration plan.

## CLAUDE.md Changes

**Remove** (move to rule files):
- Init scripts table → `layer-4-part1.md`
- Credentials section → `layer-4-part1.md` and `cross-layer.md`
- Shell section → `cross-layer.md`
- MCP section → `layer-4-part1.md` (Part 1 binary deployment) and `layer-4-part2.md` (.mcp.json pattern)
- GitHub Actions section → `layer-4-part1.md`

**Keep** in CLAUDE.md:
- Project purpose (1–2 sentences)
- 4-layer architecture diagram
- Dependency chain (Layer 1 → 2 → 3 → 4)
- Note pointing to `.claude/rules/` for layer detail
- Cross-cutting rules that apply everywhere

## Open Questions

1. **Path-scoped vs always-loaded rules**: Since Layers 1–3 are external repos managed via MCP (no local files), path-scoped rules won't fire for those layers. Options: always-loaded rules (simpler, consistent) or manual `@` import per session. TBD.

2. **Rule file depth**: How much detail belongs in rule files vs memory? Agreed: rules = "how to work with this layer now"; memory = "what we've learned and decided". No duplication.

3. **Q3 deferred**: Which repo is the primary target for this restructure — `build-with-claude` (Part 1) or `builder-project` (Part 2)? This plan covers Part 2 (builder-project) only. Part 1 restructure is a separate effort.

## Status
- [x] SessionStart hook implemented (`session-start.sh` + `settings.json`)
- [ ] CLAUDE.md restructure not started
- [ ] `.claude/rules/` files not yet created
- [ ] Pending resolution of open questions above
