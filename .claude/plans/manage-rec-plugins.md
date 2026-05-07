# /manage-rec-plugins + /manage-known-marketplaces sub-plan

Sub-plan for the plugin-management skill pair that emerges from the build-stack
absorb-analyze parent plan. Captures all SPQ (selector / rec-plugin) and MKMQ
(known-marketplaces) decisions made interactively. Authoritative source for
implementation — all open questions resolved here unless noted.

## Goal

Replace the legacy `/new-plugin-layer` skill (which built per-config L3 image
variants) with two focused skills + one shared selector lib:

| Skill | Purpose |
|---|---|
| `/manage-known-marketplaces` | Add/remove marketplace repos in `marketplaces.json` |
| `/manage-rec-plugins` | Pick which plugins make up the **single recommended L3 image** |
| (selector lib) | Shared bash UX library reused by `/build-stack` plugin selection |

Plus a new dual-source plugin delivery model:

- **Recommended L3 image** — one image, baked plugins, default for builds
- **Devcontainer features** — per-build additions on top of L2 (or recommended L3)

## Hybrid Architecture

```
                   L1 (system pkgs)
                          ↓
                   L2 (AI CLI baked in)
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
  recommended L3 image            (skip L3, build off L2)
  (anthropic/claude-plugins-       per-plugin install via
   official + caveman + curated     devcontainer features
   set baked in)
        ↓                                   ↓
        └─────────────────┬─────────────────┘
                          ↓
                  L4 (devcontainer)
                          +
              additional plugins via features
```

Build flow:
1. `/build-stack` asks "Include recommended plugins? [y/n]" first (yes/no, displays list)
2. If **no** → build off L2, every plugin installed via features
3. After recommended Y/N → optional plugin selector (additional plugins on top)
4. All non-recommended plugins delivered via devcontainer features

## File Layout (locked)

```
tools/build-stack/build_stack/data/
├── marketplaces.json          # SPQ10 — known marketplace registry
├── recommended-plugins.json   # SPQ9  — curated L3 image plugin list
└── tool-deps.json             # existing — apt resolver cache

.claude/skills/
├── _lib/
│   └── plugin-selector.sh     # SPQ12 — shared selector flow (S1–S6)
├── manage-known-marketplaces/
│   ├── manage-known-marketplaces.sh
│   └── SKILL.md
├── manage-rec-plugins/
│   ├── manage-rec-plugins.sh
│   └── SKILL.md
└── new-plugin-layer/          # SPQ11 — deprecation banner, delete after L3 verify
    └── SKILL.md  ← prepend banner
```

## marketplaces.json schema

```json
{
  "schema_version": 1,
  "marketplaces": [
    {
      "owner": "anthropics",
      "repo": "claude-plugins-official",
      "added_at": "2026-05-06T12:00:00Z",
      "default": true
    },
    {
      "owner": "user",
      "repo": "caveman",
      "added_at": "2026-05-06T12:00:00Z"
    }
  ]
}
```

## recommended-plugins.json schema

```json
{
  "schema_version": 1,
  "plugins": [
    {
      "marketplace": "anthropics/claude-plugins-official",
      "plugin": "skill-creator",
      "category": "development",
      "added_at": "2026-05-06T12:00:00Z"
    },
    {
      "marketplace": "user/caveman",
      "plugin": "caveman",
      "category": "productivity",
      "added_at": "2026-05-06T12:00:00Z"
    }
  ]
}
```

## Selector Flow (SPQ1–SPQ4, locked)

Shared UI state machine in `_lib/plugin-selector.sh`. Loops back to main loop
between menus; user can always return to start.

```
S1: Marketplace menu          → pick 1 marketplace from marketplaces.json
    ↓                            (or m) main / q) quit)
S2: Fetch marketplace          → clone --filter=blob:none --sparse, parse plugin list
    ↓                            cache under analyzed_repos/marketplaces/<owner>/<repo>/
S3: Category multi-select      → [x]/[ ] toggle by category
    ↓                            options: d) drill into selected cats
                                          s) submit-all-in-selected-cats (≥1 required)
                                          m) back to main menu
                                 (s and d both require ≥1 category selected)
S4: Drill-down cycle           → cycles per-selected-category one at a time
    ↓                            options: i <n>) info (inline metadata display)
                                          [x]/[ ] toggle individual plugins
                                          n) next selected category
                                          b) back to previous category (only if prior exists)
                                          c) return to category menu (S3)
                                          m) return to main menu
                                          f) finished, proceed to final review
S6: Final review               → list selected plugins, confirm/cancel
```

User not obligated to select anything in S4. Plugin metadata via `i <n>` shows
inline (description, author, deps preview).

Recommended plugins display tag: **`[incl. w/ recommended]`** when matching
recommended-plugins.json (SPQ5).

## Per-Plugin Analyze (SPQ7, locked)

When marketplace classified as plugin-marketplace repo, each **selected** plugin
analyzed independently:

- `python -m build_stack analyze-plugin <marketplace> <plugin>`
- Sparse checkout: `git clone --filter=blob:none --sparse <marketplace>` + `git sparse-checkout set <plugin-subdir>`
- Cache: `analyzed_repos/plugins/<owner>/<repo>/<plugin>/analysis.json`
- Aggregate caps: only **selected** plugins contribute deps to L1/L4 picking

Non-plugin repos: existing `analyze` flow (whole-repo). Marketplace classification
detected via presence of marketplace.json or plugins/ dir at repo root.

## Skill Behaviors

### /manage-known-marketplaces (MKMQ locked)

| MKMQ | Decision |
|---|---|
| MKMQ1 | Menu: a) add b) list c) remove q) quit |
| MKMQ2 | Add: prompts owner/repo, validates via `gh repo view`, fails if repo missing |
| MKMQ3 | Add: also confirms marketplace.json exists in repo root before saving |
| MKMQ4 | Remove: numbered list, confirms before deleting |
| MKMQ5 | Default seed on first run: `anthropics/claude-plugins-official` |
| MKMQ6 | No edit op (delete + re-add for changes) |

### /manage-rec-plugins (SPQ locked)

- Invokes shared selector lib pre-seeded with current recommended-plugins.json
- Allows add/remove from current recommended set
- Writes back to recommended-plugins.json on save
- Does **not** trigger image rebuild — that lives in `/deploy-stack` (bookmarked)
- Never auto-deletes (SPQ6: manual deletes only)

### /build-stack integration

Insert **before** existing plugin selection step:

```
[Step N] Include recommended plugins? [y/N]
         Recommended set:
           - anthropics/claude-plugins-official: skill-creator
           - user/caveman: caveman
           - ...
         Include all? (y/n):
```

- **y** → record `use_recommended_l3: true` in build-input.json; skip recommended plugins from later selector
- **n** → record `use_recommended_l3: false`; all plugins (including recommended ones) delivered via features

Then existing selector runs (additional plugins). Recommended-tagged plugins
shown but skippable.

Final independent prompt (SPQ8):
```
Deploy now? [y/N] (default n)
  y → invoke /deploy-stack with builds/<category>/<project>/
  n → exit, user can /deploy-stack later
```

## /new-plugin-layer Deprecation (SPQ11)

Immediate change: prepend deprecation banner to SKILL.md:

```markdown
> **DEPRECATED** — replaced by `/manage-rec-plugins` + `/manage-known-marketplaces`.
> Will be deleted after recommended L3 image rebuilt + verified end-to-end.
> Do not use for new work.
```

Delete trigger: recommended L3 image successfully built + `/build-stack` end-to-end
verified using new flow. Owned by `/deploy-stack` work item.

## Implementation Task List

Order: lib first, then skills, then build-stack integration, then deprecation.

| # | Task | Touches |
|---|---|---|
| 1 | Seed `marketplaces.json` with anthropics/claude-plugins-official | `tools/build-stack/build_stack/data/marketplaces.json` |
| 2 | Seed `recommended-plugins.json` (initial curated list TBD with user) | `tools/build-stack/build_stack/data/recommended-plugins.json` |
| 3 | Implement shared selector lib (S1–S6 state machine) | `.claude/skills/_lib/plugin-selector.sh` |
| 4 | Implement `/manage-known-marketplaces` skill | `.claude/skills/manage-known-marketplaces/` |
| 5 | Implement `/manage-rec-plugins` skill | `.claude/skills/manage-rec-plugins/` |
| 6 | Add `analyze-plugin` subcommand (sparse-checkout single plugin) | `tools/build-stack/build_stack/cli.py` + new `analyzers/plugin.py` |
| 7 | Add marketplace classifier (marketplace.json detection) | `tools/build-stack/build_stack/analyzers/manifests.py` |
| 8 | Wire recommended-plugins prompt + use_recommended_l3 flag in `/build-stack` | `.claude/skills/build-stack/build-stack.sh` |
| 9 | Wire selector lib into `/build-stack` plugin step | `.claude/skills/build-stack/build-stack.sh` |
| 10 | Update `build-input.schema.json` to add `use_recommended_l3: bool` | `tools/build-stack/build_stack/schema/build-input.schema.json` |
| 11 | Update `compose.py` to emit recommended L3 base image when flag true | `tools/build-stack/build_stack/compose.py` |
| 12 | Add deprecation banner to `/new-plugin-layer` SKILL.md | `.claude/skills/new-plugin-layer/SKILL.md` |
| 13 | Add deploy prompt at end of `/build-stack` (default n) | `.claude/skills/build-stack/build-stack.sh` |

Out of scope (bookmarked for `/deploy-stack` sub-plan):
- Recommended L3 image build/rebuild
- Plugin repo CI label backfill
- GHCR push automation
- Devcontainer rebuild trigger

## Open Items

- **Initial recommended-plugins.json contents** — needs user to pick from anthropics/claude-plugins-official + caveman. Defer until task 2.
- **`/deploy-stack` design** — separate sub-plan, not blocking this work.
- **MCP server handling** — needs design pass before implementation. See next section.

## MCP Servers — Pending Review

Stock Claude Code installs **zero MCP servers**. Four loading mechanisms exist; each interacts with the build stack differently:

| Mechanism | Source | Travels via | Stack handling |
|---|---|---|---|
| Project `.mcp.json` | `<project-repo>/.mcp.json` (committed) | git clone | Already handled — project repo provides at runtime |
| User `.mcp.json` | `~/.claude/.mcp.json` | named volume / home dir | Currently unused; portability risk if introduced |
| Plugin-bundled `.mcp.json` | `<plugin-dir>/.mcp.json` auto-loaded when plugin enabled | plugin install (baked or feature) | **Free with plugin** — e.g. baking `postman` plugin into L3 also enables postman MCP |
| claude.ai integrations | claude.ai web account (remote OAuth) | user auth, not container | Container-agnostic; rides w/ user login |

### Reference sample (this session)

| MCP appearing | Mechanism | Default w/ Claude Code? |
|---|---|---|
| `github` | project `.mcp.json` (custom) | ❌ |
| `plugin_postman_postman` | postman plugin bundled | ❌ (rides w/ postman plugin) |
| `claude_ai_Gmail` | claude.ai integration | ❌ |
| `claude_ai_Google_Drive` | claude.ai integration | ❌ |

### Open Questions (MCPQ)

| # | Question | Notes |
|---|---|---|
| MCPQ1 | Does recommended L3 ship with any MCP-bundling plugins? (postman, etc.) | Free MCPs ride along — surface to user during `/manage-rec-plugins` |
| MCPQ2 | Should `/build-stack` show "MCPs enabled by your selection" preview? | Transparency; avoids surprise MCP exposure |
| MCPQ3 | Should env-var requirements for plugin MCPs (e.g. `POSTMAN_API_KEY`) auto-merge into `credentials_required` during analyze? | Affects build-input + L4 emit |
| MCPQ4 | Should we support adding non-plugin MCPs via `/build-stack`? | E.g. user-supplied custom MCP server URL → patches project `.mcp.json` |
| MCPQ5 | Detection: does `analyze-plugin` parse `<plugin>/.mcp.json` and surface to user? | Likely yes for transparency + env-var capture |
| MCPQ6 | Per-plugin MCP env requirements: store where? | Likely `analyzed_repos/plugins/<owner>/<repo>/<plugin>/analysis.json::mcp_servers[]` |
| MCPQ7 | claude.ai integrations: in-scope at all, or strictly out-of-band? | Probably out — rides w/ auth, can't influence from container |

Defer MCPQ resolution until after core selector + skills implemented. Plug into existing analyze pipeline at MCPQ5/MCPQ6 milestones.

## Decisions Lookup (for reference during implementation)

| Q | Pick | Summary |
|---|---|---|
| SPQ1 | locked | S1→S2→S3→S4→S6 selector flow |
| SPQ2 | b | S3: single d/s, requires ≥1 cat, main-menu option |
| SPQ3 | locked | S4 cycle: i n b c m f options, b only if prior |
| SPQ4 | c+i | inline `i <n>` metadata display |
| SPQ5 | b | tag `[incl. w/ recommended]` |
| SPQ6 | b | re-enter skill to add more, manual delete |
| SPQ7 | a | per-plugin analyze, only on marketplace repos |
| SPQ8 | b | independent final deploy prompt, default n |
| SPQ9 | a | `tools/build-stack/build_stack/data/recommended-plugins.json` |
| SPQ10 | a | `tools/build-stack/build_stack/data/marketplaces.json` |
| SPQ11 | c | banner now, delete after L3 verified |
| SPQ12 | a | `.claude/skills/_lib/plugin-selector.sh` |
| MKMQ1–6 | locked | see Skill Behaviors above |
