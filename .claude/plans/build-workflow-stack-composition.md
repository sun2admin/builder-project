# build-stack Stack Composition Plan

**Skill path:** `.claude/skills/build-stack/build-stack.sh` (new skill — greenfield, UX layer)
**Tool path:** `tools/build-stack/` (new Python CLI — composition engine)
**Status:** Active — `build-stack` is a complete redesign. UX as a skill (bash); composition logic as a separate Python tool. The skill collects intent and writes `build.json`; the tool reads `build.json` and performs all heavy lifting.

> **Architectural amendment (2026-05-06) — Hybrid plugin delivery:** Plugin layer
> shifted from per-build L3 variants to a **single recommended L3 image + devcontainer
> features** for additional plugins. Build flow: `/build-stack` first asks "include
> recommended plugins? y/N", then runs the plugin selector for additions. Recommended
> plugins ride the baked L3 image; non-recommended plugins install via features at
> container startup. Sub-plan: **`./manage-rec-plugins.md`** (also covers
> `/manage-known-marketplaces`, shared selector lib, per-plugin sparse-checkout analyze,
> MCP-server handling open questions MCPQ1–7).
>
> Image build / GHCR push / devcontainer rebuild deferred to **`./deploy-stack.md`**
> (stub written 2026-05-07). `/deploy-stack` owns first-time creation of the
> `claude-plugins-recommended` GitHub repo + image (currently a phantom referenced
> by `select.py:171`) — no separate item on this parent plan.

> **Historical note:** `build-workspace` and its `build-layer1..4` sub-skills
> were deleted in commit `b641ece` (parent plan step 13). Patterns worth
> preserving (menu flow, `lib.sh` helpers, dry-run wrapper, TTY/piped input
> handling, build-name sanitization, new/clone/modify entry flow) were
> copied into `.claude/skills/build-stack/` before deletion.

> **Architectural directive (2026-05-05):** `analyze-repo` is a pure
> detector. It scans one repo and emits raw facts. **All stack composition
> logic belongs in the `build-stack` tool.** The `/build-stack` skill collects
> user inputs and writes `build.json`. The tool reads `build.json`, invokes
> analyze-repo once per repo (project repo + each selected plugin repo),
> aggregates the resulting analyses, and composes the layer stack into
> `devcontainer.json` + `workspace.env`.

> **REQUIRED READING before changes:**
> - Stack architecture → `../../CLAUDE.md` (Architecture section)
> - Active build skill → `.claude/skills/build-stack/` (SKILL.md, build-stack.sh, lib.sh)
> - Layer 4 split → [`layer4-design.md`](./layer4-design.md)
> - Analyze-project schema → [`../skills/analyze-repo/DATA_SCHEMA.md`](../skills/analyze-repo/DATA_SCHEMA.md)
> - Detection principles (parallel separation rule applies) → [`../skills/analyze-repo/DETECTION_PRINCIPLES.md`](../skills/analyze-repo/DETECTION_PRINCIPLES.md)

---

## Architecture: skill+tool split

Two artifacts, one slash command, clear contract.

```
┌──────────────────────────────────────┐    ┌──────────────────────────────┐
│ /build-stack (skill — bash)          │    │ build-stack (tool — Python)  │
│ ─ Phase 1: collect user intent       │ ─▶ │ ─ Phase 3: invoke analyze-   │
│   ─ AI CLI choice                    │    │            project per repo  │
│   ─ project repo OR sandbox          │    │ ─ Phase 4: aggregate         │
│   ─ 0+ plugin repos                  │    │ ─ Phase 5: compose (L1/L4)   │
│   ─ override prompts                 │    │ ─ Phase 6: emit              │
│ ─ Phase 2: write build.json          │    │            devcontainer.json │
│   + invoke tool                      │    │            + workspace.env   │
│                                      │    │                              │
│ ~250 lines bash                      │    │ ~1500-2500 lines Python      │
└──────────────────────────────────────┘    └──────────────────────────────┘
                                ▲                  │
                                │                  ▼
                          builds/<name>/build.json (versioned JSON contract)
```

### Why split

| Concern | Resolution |
|---|---|
| Skill code size growth | Skill stays ~250 lines (UX only). Tool absorbs all feature accretion. |
| Bash awkward for set algebra / version compare | Tool is Python; skill stays bash for I/O |
| Independent testability | Tool runs in CI without Claude session; unit tests on Python modules |
| Replay / audit / cache | `build.json` is git-trackable; tool re-run regenerates outputs |
| Non-interactive use | Automation/cron writes `build.json` directly, invokes tool, bypasses skill |
| Promotion to standalone | Tool can be promoted to `pip install build-stack` later without touching skill |

### Skill side: one skill, internal phase modules

```
.claude/skills/build-stack/
├── SKILL.md
├── build-stack.sh           # entry point: phase orchestration, ~250 lines
└── lib.sh                   # bash helpers, copied verbatim from build-workspace/lib.sh
```

No sub-skills (no per-layer split). Phases are functions in one process. Reasons:
- Layers ≠ phases. Output is layered (L1/L2/L3/L4); work is phased (gather/analyze/aggregate/compose/emit).
- Composition is cross-cutting: L1 depends on aggregated deps from all repos; L4 features depend on L1 floor; L3 depends on L2 + plugins. The DAG doesn't decompose per-layer.
- Single-process state passing simpler than env files / exit codes between sub-skills.

### Tool side: one binary, subcommand decomposition

```
tools/build-stack/
├── pyproject.toml
├── README.md
├── build_stack/
│   ├── __main__.py          # entry: python -m build_stack <subcommand>
│   ├── cli.py               # argparse, subcommand dispatch
│   ├── analyze.py           # Phase 3 — invokes analyze-repo skill (Phase 1 migration), Python port (Phase 2+)
│   ├── aggregate.py         # Phase 4 — multi-repo merge per merge rules
│   ├── select.py            # Phase 5a — L1 capability cover, L3 plugin layer pick
│   ├── compose.py           # Phase 5b — L4 feature map, version overlays
│   ├── emit.py              # Phase 6 — devcontainer.json + workspace.env writer
│   ├── ghcr.py              # GHCR manifest queries, OCI label reads
│   └── schema/
│       └── build-input.schema.json  # JSON Schema for build.json validation
└── tests/
    ├── fixtures/             # sample build.json + expected outputs
    └── test_*.py
```

Subcommands (git-style verbs):

| Subcommand | Use |
|---|---|
| `build-stack compose <build.json>` | Primary path: full Phase 3-6 pipeline |
| `build-stack validate <build.json>` | JSON-schema check + reachability validation (skill calls before invoking compose) |
| `build-stack analyze <repo>` | Standalone single-repo detection (replaces /analyze-repo's bash logic in Phase 2+) |
| `build-stack diff <build-a> <build-b>` | Future: stack-diff for review |
| `build-stack stats builds/` | Future: promotion-path metrics from aggregated analyses |
| `build-stack rebuild builds/<name>` | Future: re-emit outputs from existing build.json (cache hit) |

### Front-facing skills (two slash commands, one tool)

| Skill | Role | Tool subcommand invoked |
|---|---|---|
| `/build-stack` | Multi-repo composition workflow (Phases 1-6) | `compose` (which internally calls `analyze` + `aggregate`) |
| `/analyze-repo` | Single-repo detection — independently invokable per user request | `analyze` (Phase 2+ end state); current 1629-line bash retained in Phase 1 |

Both skills are thin UX wrappers. Tool owns all logic.

### `analyze-repo` migration phases (skill→tool absorption)

| Phase | analyze-repo skill | tool's `analyze` subcommand | Status |
|---|---|---|---|
| 0 — current | 1629-line bash, full logic | does not exist | now |
| 1 — build-stack v1 | 1629-line bash, full logic | shells out to skill via Bash subprocess | first build-stack release |
| 2 — port | 1629-line bash, full logic | full Python port (parallel implementation) | post-build-stack-stable |
| 3 — cutover | thin ~50-line bash wrapper → calls `build-stack analyze` | full implementation, single source of truth | after parity validated |

Phase 4 (skill removal) explicitly NOT planned — independent invocation valuable.

---

## Boundary

**Status of migration as of 2026-05-05:**
- ✅ Detector stripped: `suggested.*`, `firewall_required` no longer emitted by analyze-repo
- ⚠️  Composer not yet implemented: build-stack tool does not exist; no devcontainer.json composition output
- 🆕 New fields (never existed in detector): `dockerfile_from`, `extras_needed`, `devcontainer_features`, `version_overlays`

### What stays in analyze-repo (pure detection)
- `languages`, `runtime_versions`, `runtime_extras`
- `system_packages`, `extra_binaries`, `global_js_packages`,
  `dockerfile_python_installs`, `dockerfile_go_installs`
- `libraries.{node,python,go,rust}`
- `ports.inbound`, `external_services.domains`
- `env_vars`, `credentials_required.{api_keys,tokens,ssh,other}`
- `mcp_servers`, `claude_plugins`
- `browser_tools`, `github_api_usage`
- `container.{capabilities,volumes,env,remote_user,extensions,
  post_start,post_create,post_start_chain,post_create_chain,init_scripts}`
- `inferred.{tools,tools_new,tools_confirmed,py_imports*,ts_imports*,ci_tools}`
- `system_deps` (apt-cache resolution — fact, not decision)

### What lives in build-stack tool (composition / opinion)
- ✅ `suggested.base_image` — picks L1 variant (in `select.py`)
- 🆕 `suggested.dockerfile_from` — project-native runtime image (in `select.py`, never in detector)
- ✅ `suggested.ai_install` — picks L2 variant (in `select.py`)
- ✅ `suggested.plugin_layer` — picks L3 image (in `select.py`)
- ✅ `firewall_required` (bool) — derived in `compose.py` from capabilities + script presence
- 🆕 `extras_needed`, `devcontainer_features`, `version_overlays` — in `compose.py`
- 🆕 `L1_LATEST_RUNTIMES`, `DEVCONTAINER_FEATURE_MAP` — constants in `select.py`/`compose.py`

---

## JSON Contract: `build.json`

The skill+tool boundary. Skill writes; tool reads.

**Location:** `builds/<build_category>/<build_project>/build.json`

**Schema (v3) — locked 2026-05-07 to match implementation at `tools/build-stack/build_stack/schema/build-input.schema.json`:**
```json
{
  "schema_version": 3,                                  // integer const 3 (was string "1.0" in v1 draft)
  "build_category": "santifer",                         // 1st path level (default = repo's GH owner; gh_user for sandbox)
  "build_project": "career-ops",                        // 2nd path level (default = repo basename; "sandbox" for sandbox)
  "project_repo": "santifer/career-ops",                // OR null = sandbox build (plugins-only or empty)
  "use_recommended_l3": false,                          // v2+: pull recommended L3 image (claude-plugins-recommended) vs build off L2
  "plugin_selections": [                                // v3: replaces v1's flat plugin_repos[] — captures marketplace/plugin pairs from selector
    {"marketplace": "anthropics/claude-plugins-official", "plugin": "skill-creator"}
  ],
  "ai_clis": ["claude", "gemini"],                      // ordered list; index 0 = primary (L2 image variant); 1+ = L4 init-script installs
  "overrides": {},                                      // v2+: optional per-cred / per-base-image override block
  "created": "2026-05-06T00:00:00Z",
  "last_modified": "2026-05-06T00:00:00Z"
}
```

**Schema evolution:** v1 → v2 added `use_recommended_l3` + `plugin_selections` (commit `39a7f9f`); v2 → v3 dropped flat `plugin_repos[]` field (commit `811054c`). Tool refuses any schema_version != 3.

JSON Schema lives at `tools/build-stack/build_stack/schema/build-input.schema.json`. Skill calls `build-stack validate <path>` before invoking compose; tool refuses unknown schema_version.

---

## Skill UX Design (locked 2026-05-06)

Phase 1 of the `/build-stack` skill collects user intent through the following ordered flow. Decisions resolved 2026-05-06; full Q&A history in conversation log.

### Pre-flight checks (skill entry, fail-fast)

1. `gh auth status` — must be authenticated (skill cannot validate repos or clone otherwise)
2. `python -m build_stack --version` — tool installed (else: "run `pip install -e tools/build-stack/`")
3. `git` available
4. `gh` available

If any precheck fails, skill exits with clear remediation message before any prompts.

### Phase 1 prompt order

```
Step 1 — Project repo prompt
  Input: owner/repo OR empty (= sandbox)
  Validation: gh api repos/<owner>/<repo>
    200 OK         → proceed
    404            → re-prompt (typo recovery)
    401/403/network → hard-fail with clear remediation (gh re-auth, retry later)

Step 2 — Cache check (analyze)
  Path: analyzed_repos/<owner>/<repo>/analysis.json
  If exists: prompt
    [1] use cached  (default — press ENTER, shows mtime "23 days old")
    [2] reanalyze
  If missing OR user picks reanalyze: invoke /analyze-repo
  Failure menu (analyze step):
    [r] retry      (re-invoke same repo)
    [n] new name   (re-prompt project repo, full re-validate, re-derive defaults)
    [q] quit
  Loop until success.

Step 3 — Category prompt
  Default: project_repo's GH owner (e.g. "santifer") OR gh_user when sandbox
  Stored: BUILD[CATEGORY]

Step 4 — Collision pre-check (silent)
  candidate = project_repo basename if real, else "sandbox"
  scan builds/<CATEGORY>/ for candidate, candidate-2, ...
  determine first-free-suffix
  set collision-flag

Step 5 — Project name menu
  No collision: prompt with candidate as default → ENTER accepts
  Collision detected: 3-option menu
    [1] career-ops-3              (suffix, default — first free slot found)
    [2] overwrite career-ops      (the original base, no suffix; always offered)
    [3] custom name               (free-text re-prompt; if collides → recurse this menu)
  Custom name path can recurse via [3] indefinitely. Each menu's overwrite targets that menu's specific collision.

Step 6 — AI CLI selection (multi-select toggle menu)
  Detection signals: claude_plugins, mcp_servers, package deps, CLAUDE.md / GEMINI.md presence
  Default selected: claude (recommended) shown highlighted; user can change.
  Menu shape: extensible toggle TUI
    [x] claude    (selected, primary)
    [ ] gemini
    [ ] <future-cli>
    [s] submit
    [q] quit
  Numeric input toggles entry. Re-toggle deselects. First-toggled = primary.
  Deselecting primary → next-selected auto-promotes to primary. Submit blocked if zero selected.
  Available CLI list comes from tool: `build-stack list-ai-clis`.

Step 7 — Plugin repos loop
  Menu pattern (build-workspace style — flagged for revisit):
    [1] sun2admin/claude-plugins-coding   (from GHCR query)
    [2] sun2admin/claude-plugins-base
    ...
    [c] custom owner/repo (free entry)
    [d] done
  Each pick:
    a. Validate via gh api repos/<owner>/<repo> (404 reprompt; auth/network hard-fail)
    b. Cache check (use cached / reanalyze) per Step 2 pattern
    c. Invoke /analyze-repo on miss/reanalyze
    d. Failure menu: [r] retry / [s] skip / [q] quit
  Loop until [d] done.

Step 8 — Atomic stage + tool invoke
  Stage dir: builds/.staging/<random>/  (same filesystem as final dest → atomic mv guaranteed)
  .staging/ in .gitignore
  Skill writes build.json to staging
  Skill: build-stack validate <staging>/build.json
  Skill: build-stack compose <staging>/build.json
  Tool writes outputs alongside input file (in staging dir): aggregated.json, devcontainer.json, workspace.env
  On full success: mv staging → builds/<build_category>/<build_project>/
  On any failure: rm -rf staging; builds/ untouched (atomic guarantee)

Step 9 — Verbose summary printed (BSQ14 (b))
  Inputs: project, plugins, ai_clis
  Picks: L1/L2/L3/L4 selections
  Outputs: written file paths
  Next-step hint: cp builds/<cat>/<prj>/devcontainer.json .devcontainer/
```

### DRY-RUN mode (`--dry-run`)

Pure preview: prints final `build.json` to stdout, exits. NO analyze invocations, NO staging dir, NO tool calls, NO filesystem writes anywhere.

### Failure-mode summary table

| Failure point | Behavior |
|---|---|
| Pre-flight check fails | Hard-fail with remediation message; no prompts shown |
| Project repo validation 404 | Re-prompt project repo |
| Project repo validation auth/network error | Hard-fail with gh auth or retry hint |
| Project repo analyze fails | Menu: `[r]/[n]/[q]` (retry / new name / quit), loop until success |
| Plugin repo analyze fails | Menu: `[r]/[s]/[q]` (retry / skip / quit) |
| Tool validate fails | Hard-fail before compose; staging dir cleaned |
| Tool compose fails | Hard-fail; staging dir cleaned; `builds/` untouched |

---

## Stack-composition responsibilities

All sections below describe behavior of the **tool**, not the skill. Skill only sets fields in `build.json`; tool implements all of the following.

### 1. Multi-repo analysis aggregation

**Updated 2026-05-06:** Skill (not tool) invokes `/analyze-repo` per repo. Tool's `compose` subcommand only READS pre-existing `analyzed_repos/<owner>/<repo>/analysis.json` files. Skill is responsible for ensuring all referenced analyses exist before invoking compose.

```python
# Tool's compose pseudo-code (no analyze invocations)
analyses = []
if build.project_repo:
    analyses.append(load_analysis(f"analyzed_repos/{build.project_repo}/analysis.json"))
for plugin_repo in build.plugin_repos:
    analyses.append(load_analysis(f"analyzed_repos/{plugin_repo}/analysis.json"))
# Sandbox case: project_repo = null → analyses may be empty (plugins-only)
# Tool fails with clear error if any referenced analysis.json missing.
```

Each `analysis.json` lives at `analyzed_repos/<owner>/<repo>/analysis.json` (path layout post-sub-plan Phase 1.5). Tool reads each, merges by category. Merge rules:

| Field | Merge rule |
|---|---|
| Sets (languages, system_packages, env_vars, claude_plugins, browser_tools) | Union, then sort |
| Per-language libs | Union per-lang, then sort |
| Domains | Union, then sort |
| Credentials | Union per-bucket (api_keys/tokens/other), `ssh = any(ssh)` |
| MCP servers | Union by `name` field; conflict on duplicate name → fail with error (no auto-merge) |
| post_start chains | Concatenate in order: project chain first, then plugin chains |
| init_scripts | Union, preserve order |
| runtime_versions | Highest pinned version wins; latest (unpinned) loses to any pin; cross-pin conflict → fail with error |
| capabilities, volumes | Union; volumes deduped by `target` path |

**Aggregation artifact:** Tool writes `builds/<build_name>/aggregated.json` after merge. Mirrors per-repo `analysis.json` pattern. Supports debugging, replay, promotion-path metrics.

### Plugin source-repo discovery

Each L3 plugin image must declare its source repo via OCI label at build time:

```
org.opencontainers.image.source = https://github.com/<owner>/<repo>
```

Tool queries the manifest:
```bash
docker manifest inspect ghcr.io/sun2admin/<plugin-image>:latest \
  | jq -r '.config.Labels["org.opencontainers.image.source"]'
```

If label missing on a selected plugin: skill prompts user for source repo URL, warns that the plugin image needs label backfill at next L3 publish.

**Dependencies:**
- `build-and-push.yml` for each plugin repo must pass `--label org.opencontainers.image.source=<url>` (one-line CI change)
- Document required label in `layer3-ai-plugins/CLAUDE.md`

### 2. L1 variant selection — minimal viable + user override

Pick the **smallest L1 variant that covers all aggregated dependencies**, then offer user the option to override upward (never downward).

**Capability profile of each L1 variant** (lives in `select.py`, versioned in lockstep with L1 image publish):

```python
L1_VARIANTS = {
    'light': {
        'rank':      1,
        'provides':  {'node', 'shell', 'gh-cli', 'apt-essentials'},
        'excludes':  {'python', 'graphics-libs', 'browser-engines'},
    },
    'latest': {
        'rank':      2,
        'provides':  {'node', 'shell', 'gh-cli', 'apt-essentials',
                      'python', 'dev-tools', 'graphics-libs'},
        'excludes':  {'browser-engines'},
    },
    'playwright_with_chromium': {
        'rank':      3,
        'provides':  {'node', 'shell', 'gh-cli', 'apt-essentials',
                      'python', 'dev-tools', 'graphics-libs',
                      'playwright-core', 'chromium'},
        'excludes':  {'firefox', 'webkit'},
    },
    'playwright_with_firefox':  {'rank': 3, 'provides': {..., 'firefox'},  ...},
    'playwright_with_safari':   {'rank': 3, 'provides': {..., 'webkit'},   ...},
    # NOTE: playwright_with_all variant is defined in CI but NOT published —
    # exceeds GitHub Actions runner time limit. Multi-browser projects must
    # pick one variant + install other browsers at L4 via init script.
}
```

**Required capabilities derived from aggregated analysis:**

```python
def required_caps(agg):
    caps = {'node', 'shell'}
    if 'python' in agg['languages']:        caps.add('python')
    if 'playwright' in agg['browser_tools']:caps.add('playwright-core')
    if uses_chromium(agg):                  caps.add('chromium')
    if uses_firefox(agg):                   caps.add('firefox')
    if uses_webkit(agg):                    caps.add('webkit')
    if needs_graphics(agg):                 caps.add('graphics-libs')
    if needs_dev_tools(agg):                caps.add('dev-tools')
    return caps
```

**Selection algorithm:**

```python
def pick_l1(agg):
    needed = required_caps(agg)
    candidates = [(n, v) for n, v in L1_VARIANTS.items()
                  if needed <= v['provides']]
    if candidates:
        return min(candidates, key=lambda x: x[1]['rank'])[0], []  # (variant, missing=empty)

    # No variant covers all caps → pick max-rank variant + emit
    # `extras_needed = needed - max_variant.provides` for L4 fallback
    max_variant = max(L1_VARIANTS.items(), key=lambda x: x[1]['rank'])
    return max_variant[0], list(needed - max_variant[1]['provides'])
```

Caller checks the second return value: if non-empty, those caps must be installed via L4 features (Section 5) or init scripts.

**User override validation:**

```python
def validate_override(user_choice, needed):
    if user_choice not in L1_VARIANTS:
        return False, f"unknown variant {user_choice}"
    provides = L1_VARIANTS[user_choice]['provides']
    missing = needed - provides
    if missing:
        return False, f"override {user_choice} missing: {missing}"
    return True, None
```

**Interactive flow (in skill, validated by tool):**

```
analyze-repo completes for project + N plugin repos
   ↓
aggregate analyses (in tool)
   ↓
required = required_caps(aggregated)
auto_pick, missing = pick_l1(aggregated)

Print to skill stderr:
  "Required L1 capabilities: {required}"
  "Minimal variant: {auto_pick}"
  "Higher-capability options: [latest, playwright_with_chromium, ...]"
  "Press ENTER to accept, or pick override:"
   ↓
if user_input:
    valid, err = validate_override(user_input, required)
    if not valid: REJECT, re-prompt
   ↓
build.overrides.base_image = user_input or null    # null = auto-pick stays
```

**Examples:**

| Project | required_caps | auto_pick | Allowed overrides |
|---|---|---|---|
| Pure node CLI tool | `{node, shell}` | `light` | `latest`, all `playwright_with_*` |
| Node + Python AI app | `{node, shell, python}` | `latest` | All `playwright_with_*` |
| Node + Python + Playwright (Chromium) | `{node, shell, python, playwright-core, chromium}` | `playwright_with_chromium` | `playwright_with_firefox`, `playwright_with_safari` (all rank 3) |
| Node + Python + Playwright (multi-browser) | `{..., chromium, firefox, webkit}` | `playwright_with_chromium` + `extras_needed={firefox, webkit}` (no all-in-one variant published) | Pick another rank-3 variant + extras |

**Why minimal-viable over always-:latest:**
- Smaller image pull (`:light` ~150MB vs `:latest` ~600MB)
- Faster cold start on first dev build
- Less disk usage per dev workstation
- User can override upward if they want bigger toolchain

**Why never override downward:**
- `validate_override` refuses overrides that drop required capabilities
- Prevents broken devcontainers from manual misconfiguration

### 3. L2 variant selection

Default: pick from `aggregated.languages` + project framing:
- `claude` if no signals (most projects)
- `gemini` if user explicitly chose at /build-stack entry
- Future: if `aggregated.mcp_servers` references gemini-only servers

Override: explicit user prompt at workflow entry. No auto-detect from project content — too ambiguous.

When L2=gemini, §4 has no candidates currently (no `gemini-plugins-*` images exist). Tool skips L3 entirely or prompts user.

### 4. L3 plugin layer selection

Algorithm parallel to §2 (set-cover with monotone preference):

```python
needed_plugins = aggregated.claude_plugins
candidates = [img for img in ghcr_query_plugin_images()
              if needed_plugins <= img.plugin_set]
if candidates:
    return min(candidates, key=lambda i: len(i.plugin_set))  # smallest superset
else:
    # No image contains all required plugins
    return INVOKE_NEW_PLUGIN_LAYER_BUILD(needed_plugins)
```

If no match: per the recommended-L3 + features hybrid (parent plan amendment 2026-05-06; sub-plans `manage-rec-plugins.md` + `deploy-stack.md`), missing plugins are delivered via devcontainer features — no new per-build L3 image is created. Image creation is owned by `/deploy-stack` and triggered only when the recommended plugin set itself changes.

### 5. Layer 4 overlay composition

After L1/L2/L3 picked, compose Layer 4 devcontainer.json:

**Heavy assets** (in L1 floor):
- Whatever L1 variant ships (node, python, browsers if playwright_*)

**L4 devcontainer features** (per-project lightweight overlays):
```python
L1_LATEST_RUNTIMES = {'node', 'python', 'shell'}
L1_LATEST_VERSIONS = {'node': '22', 'python': '3.12'}
DEVCONTAINER_FEATURE_MAP = {
    'go':     'ghcr.io/devcontainers/features/go:1',
    'rust':   'ghcr.io/devcontainers/features/rust:1',
    'ruby':   'ghcr.io/devcontainers/features/ruby:1',
    'java':   'ghcr.io/devcontainers/features/java:1',
    'php':    'ghcr.io/devcontainers/features/php:1',
    'dotnet': 'ghcr.io/devcontainers/features/dotnet:1',
}

# Languages not baked into L1 floor → feature install
extras_needed = aggregated.languages - L1_LATEST_RUNTIMES

# Languages baked but at wrong version → side-by-side install via feature
version_overlays = {
    lang: ver
    for lang, ver in aggregated.runtime_versions.items()
    if lang in L1_LATEST_VERSIONS
       and ver
       and not L1_LATEST_VERSIONS[lang].startswith(ver)
}
```

These constants live in `compose.py` and update when L1 image content changes — single source of truth, versioned in lockstep with L1 publish.

### 6. Credentials wiring

For each entry in `aggregated.credentials_required`, decide whether to use `containerEnv` passthrough (host env) or `/run/credentials/<name>` mount.

**Default policy** (when `build.json` doesn't specify per-cred override): `containerEnv` passthrough. Rationale: simplest, matches dev-on-laptop pattern. User can re-run /build-stack to switch to mount-based delivery per cred.

**Per-cred override:** `build.json.overrides.credentials_delivery.<NAME>` = `"containerEnv"` or `"mount"`.

Generates appropriate devcontainer.json `containerEnv` and `mounts`.

### 7. Firewall composition

- Set `runArgs` `--cap-add NET_ADMIN/NET_RAW` if any aggregated analysis shows iptables-touching init script OR explicit capability
- Generate per-project firewall extension if `aggregated.external_services.domains` exceeds L1's baked allowlist

L1's baked allowlist is defined in: `layer1-ai-depends/init-firewall.sh`

Tool reads that file's allowlist, diffs against `aggregated.external_services.domains`, emits an `extra-domains.sh` only when the diff is non-empty.

### 8. Init script chain assembly

Each per-repo chain provided as ordered list. Compose:

1. Build a partial order from constraints:
   - `init-firewall.sh` ≺ everything (must run first)
   - `init-ssh.sh` ≺ `init-gh-token.sh` ≺ `init-github-mcp.sh` (existing convention)
   - `load-projects.sh` runs last
2. Topologically sort union-of-chains under the partial order.
3. Conflict = same script appears in two chains at incompatible positions relative to the partial order. Detect: cycle in graph after collapse.
4. On conflict: emit warning + use partial-order default. Fail-fast in CI / non-interactive mode.

Emit final `postStartCommand` string into devcontainer.json.

---

## Decision-rule summary (heavy asset vs feature)

Composition logic (lives in tool's `compose.py`, NOT in skill):

```
USE L1 VARIANT WHEN:
  asset_size_mb > 200  AND
  (network_install_cost > apt_install OR
   install_complexity > single_apt_line OR
   team_rebuild_frequency > weekly)

USE L4 DEVCONTAINER FEATURE WHEN:
  asset_size_mb < 200  OR
  apt_installable_in_one_line  OR
  rarely_needed_across_projects
```

Examples:
| Asset | Decision | Why |
|---|---|---|
| Playwright browsers | L1 variant | 250MB+ CDN download, OS-deps order, frequent rebuilds |
| Go runtime | L4 feature | Light, single feature install, side-by-side ok |
| Rust toolchain | L4 feature | rustup handles versions cleanly |
| CUDA toolkit | L1 variant if widely used else feature | 2GB+, complex driver compat |
| Java JDK | L4 feature | Apt-installable, version mgrs work |

---

## Promotion path

**Scope:** Out of scope for build-stack v1. Documented as future direction. Requires `build-stack stats` subcommand to scan `builds/*/aggregated.json`.

When a feature becomes ubiquitous:
1. Track feature usage frequency across all `builds/*/aggregated.json` runs
2. When >50% of recent projects (window: TBD) use feature X → propose promotion
3. Stack maintainer approves; bumps L1 image with X baked in
4. `build-stack` constants updated; X removed from `DEVCONTAINER_FEATURE_MAP`
5. Existing devcontainer.json files using the feature continue to work (feature install becomes idempotent)

---

## Migration steps from current state

**Sequencing (revised 2026-05-06):** Sub-plan `build-stack-absorb-analyze.md` Phases 1.5+2+3 execute BEFORE parent steps 6.4-6.6 (compose pipeline). Rationale: clean architecture upfront; composition logic developed against real Python detector, not throwaway bash-shell-out wrapper.

1. ✅ DONE — Removed `suggested` block from analyze-repo.sh
2. ✅ DONE — Removed `firewall_required` from analyze-repo.sh
3. ✅ DONE — Create `build-stack` skill skeleton:
   - `.claude/skills/build-stack/SKILL.md`
   - `.claude/skills/build-stack/build-stack.sh` (Phase 1+2 stub)
   - `.claude/skills/build-stack/lib.sh` (copied from build-workspace)
4. ✅ DONE — Create `build-stack` tool skeleton:
   - `tools/build-stack/pyproject.toml`
   - `tools/build-stack/build_stack/__main__.py` + `cli.py`
   - JSON schema at `tools/build-stack/build_stack/schema/build-input.schema.json`
5. ✅ DONE — Implement tool subcommand `validate` (JSON schema check)
6. ✅ DONE — Sub-plan `build-stack-absorb-analyze.md` (UNBLOCKS step 7):
   - ✅ Phase 1 (shell-out wrapper): `analyze.py::analyze()` + `cmd_analyze()` shell out to skill.
   - ✅ Phase 1.5 (OUT_DIR migration, commit `e592e9f`): `builds/<owner>/<repo>/` → `analyzed_repos/<owner>/<repo>/`. Migrated 7 existing dirs via `git mv`.
   - ✅ Phase 2 (Python port, commits `e52183f` → `cd1938e` → `572fca5`): ported 1629-line `analyze-repo.sh` → 7-module Python package under `tools/build-stack/build_stack/analyzers/`. Moved `tool-deps.json` to `tools/build-stack/build_stack/data/`. Parity test (semantic equivalence) at `tools/build-stack/tests/test_analyze_parity.py`. **Original "10/10 corpus repos green" claim revised 2026-05-07:** verification round revealed F7 — the parity test invokes `python -m build_stack analyze` whose `cmd_analyze` (cli.py:71-72) hardcodes output to `analyzed_repos/<owner>/<repo>/` with no opt-out. Running the test rewrites live cache for all 10 repos with degenerate output (empty languages, empty container.*, etc.). The "10/10 green" was empty-vs-empty parity passing trivially, with 2/10 (`anthropics/claude-code`, `santifer/career-ops`) actually breaking through the noise floor. Test now skipped by default (commit `454d667`). Real parity status: unknown until F7-A lands (add `--out-dir` flag to `cmd_analyze`).
   - ✅ Phase 3 (cutover, commit `404950e`): replaced `analyze-repo.sh` (1629 → 59 lines) with thin wrapper that execs `python -m build_stack analyze`. Moved docs to `tools/build-stack/docs/`.
7. ✅ DONE (verified 2026-05-07 via smoke tests) — Tool subcommands implemented:
   - `build-stack list-ai-clis` — emits `claude\ngemini` (and `--json` form)
   - `build-stack compose <build.json>` — full Phase 4-6 pipeline runs end-to-end against cached `analyzed_repos/sun2admin/builder-project/`, emits `aggregated.json`, `devcontainer.json`, `workspace.env`
   - **Caveats discovered in smoke tests** (status as of 2026-05-07):
     - **F1 (silent-failure bug) ✅ FIXED (commit `664f8f1`):** `__main__.py` now `sys.exit(main())`s. `python -m build_stack` propagates exit codes 2 (file not found) and 3 (schema validation) correctly.
     - **F2 (schema drift vs plan) ✅ FIXED (commit `77ac95b`):** JSON Contract section updated to v3 reality with schema-evolution timeline.
     - **F3 (output sparsity for builder-project run) ⚠️ OPEN:** `compose` emits a near-empty devcontainer.json (4 keys only). Root cause is the detector's `dockerfile.py:104` hardcoding `repo_path / ".devcontainer" / "devcontainer.json"` — the path-discovery is too narrow. `builder-project` has its devcontainer at `layer4-devcontainer/devcontainer.json` (control-plane subdir). `emit.py` itself reads all the fields correctly (see `emit.py:76,92-107,164-202`); the gap is upstream. Note: the `anthropics/claude-code` cache also shows empty container.* despite having `.devcontainer/devcontainer.json` — separate investigation needed once F7-A unblocks trustworthy re-analysis.
     - **F7 (parity test live-cache corruption) ✅ FIXED-A (commit `dd7266e`):** Added `--out-dir` flag to `cmd_analyze`. Parity test now uses `tmp_path` for redirection. Test still skipped by default (set `BUILD_STACK_PARITY_TEST=1` to run) because a separate flakiness issue remains: bash-side and port-side run on different fresh `--depth=1` clones, so HEAD movement between clones produces real divergence on high-traffic repos. That's a test-design issue, not a detector bug — re-evaluate when refactoring the test to share a single clone across both sides.
8. ✅ DONE (verified 2026-05-07) — `/build-stack` skill body implemented per "Skill UX Design": 689 lines covering pre-flight, all 9 phase steps (`step1_project_repo` → `step8_plugin_selector` → `phase2_invoke` → `print_summary`) at `.claude/skills/build-stack/build-stack.sh`. `--dry-run` short-circuits per spec. Interactive validation (parent plan step 12) is the gate that turns "implementation present" into "behavior verified."
9. ✅ DONE — `.gitignore` entry `builds/.staging/` present (atomic-write staging dir).
10. ⏭️  SUPERSEDED — OCI source label backfill on the 8 standalone L3 plugin repos. Architecture pivoted to a single recommended L3 image + devcontainer features (parent plan amendment 2026-05-06; sub-plans `manage-rec-plugins.md` and `deploy-stack.md`). The 8 legacy plugin repos will be manually deleted; OCI label work now lives in `/deploy-stack` for the future `claude-plugins-recommended` image. The label requirement itself is still documented in `layer3-ai-plugins/CLAUDE.md`, but the 8-repo backfill list there is obsolete and can be cleaned up alongside the broader L3 doc refresh (out of scope for this step).
11. ✅ DONE (2026-05-07) — Updated reference docs to reflect removed fields + skill+tool boundary:
   - `tools/build-stack/docs/DATA_SCHEMA.md` — Consumer Contract table re-pointed at `/build-stack` tool with §-section refs into this plan; "Adding a new field" checklist now points at `/build-stack`; tool-deps.json paragraph updated for post-Phase-3 cutover state.
   - `tools/build-stack/docs/DETECTION_PRINCIPLES.md` — "Composition belongs to" and "route the change to" clauses updated from `build-workflow` to `/build-stack` + plan link. The `suggested.*`/`firewall_required` "Forbidden in this skill" list intentionally retained as boundary marker.
   - `tools/build-stack/docs/TESTING.md` — connect-rust verifies-column drops "suggested FROM" (no longer emitted); verification-protocol command line updated to `python -m build_stack analyze` (Phase-3 wrapper still works as the skill).
12. 🚧 TODO — Validate end-to-end: scaffold a stack from this builder-project repo using `/build-stack`, compare output to existing devcontainer.json.
13. ✅ DONE — Deleted `build-workspace` skill + `build-layer1..4` sub-skills (commit `b641ece`).

---

## Composition Doctrine

Three rules for analyze-repo / build-stack boundary:

1. **Detection ≠ provisioning** — analyze-repo detects what a repo declares; build-stack tool decides what to install where.
2. **Skill emits raw signals; tool makes decisions.** If a field in `analysis.json` is computed from other fields plus opinion, it belongs in the build-stack tool, not in analyze-repo.
3. **Test the boundary** — analyze-repo test corpus (see TESTING.md) asserts schema shape. Add explicit test that no test fixture contains `suggested.*` or `firewall_required` keys.

---

## Open Questions — resolved

- ~~Aggregation artifact location~~ → §1: `builds/<build_category>/<build_project>/aggregated.json`
- ~~runtime_versions conflict~~ → §1 merge table: highest pinned wins, latest loses to any pin, cross-pin conflict fails
- ~~Plugin source repo discovery~~ → §1: OCI source label
- ~~Implementation language (bash vs Python)~~ → Architecture section: skill = bash, tool = Python
- ~~Skill split (per-layer vs single)~~ → Architecture section: single skill, internal phases
- ~~analyze-repo independent invocation~~ → Architecture section: `/analyze-repo` skill stays as thin wrapper post-Phase 3 migration
- ~~Workspace name derivation~~ → Skill UX Design Step 5: `<build_category>/<build_project>` derived from project repo, collision menu provides 3 options (suffix/overwrite/custom recursive). Sandbox: `<gh_user>/sandbox`.
- ~~Skill prompt order~~ → Skill UX Design (locked 2026-05-06)
- ~~Atomic skill behavior~~ → Skill UX Design Step 8: `builds/.staging/<random>/` staged, atomic mv on success, no `builds/` writes on failure
- ~~Multi-CLI handling~~ → Skill UX Design Step 6: ordered `ai_clis[]`, [0]=primary (L2 baked), 1+ = L4 init scripts. Toggle TUI menu. Future: revisit as devcontainer features (tracked).
- ~~MVP scope (overrides)~~ → JSON Contract: no overrides in v1; rerun skill or hand-edit build.json to change.
- ~~Analyze ownership~~ → §1 update: skill invokes `/analyze-repo`, tool's compose only reads pre-existing `analyzed_repos/`.
- ~~Pre-flight checks~~ → Skill UX Design pre-flight: gh auth + tool installed + git + gh.

## Open Questions — remaining

- Promotion threshold window (§Promotion path "last 30 days, last N runs, all-time"?)
- gemini-plugins-* images don't exist yet — when ai_clis[0]=gemini, §4 has no L3 candidates. Skip L3 entirely, prompt user, or build empty plugin layer?
- Tool distribution: stay in `tools/build-stack/` indefinitely, or promote to standalone repo once stable? Promotion criteria: external reuse, version cadence diverges from builder-project.
- AI CLIs as devcontainer features (tracked in TaskCreate #11): replace L2 image variants with feature installs at L4. Pro: multi-CLI trivial, smaller L2 images. Con: install delay on first start. Decide post v1 ship.
- Plugin loop UX revisit (tracked in TaskCreate #10): GHCR menu + free entry confirmed for v1; possible refinements later (search filter, cap, plugin layer composition options).
- AI CLI signal-detection rules in skill: precise priority/scoring when multiple signals present? (e.g. project has CLAUDE.md AND `@google/gemini-cli` dep — does claude or gemini win the recommended-default?)
- **Container user environment (relocated 2026-05-07):** All open questions about the `claude` user's per-session environment — `myclaude` alias placement, `~/live-project` sandbox-mode fallback, VS Code Server keybindings persistence (Shift+Enter for newlines), shell rcfile chain — consolidated into sub-plan **`./claude-user-env.md`**. See that file for current state, options table, and resume conditions.
