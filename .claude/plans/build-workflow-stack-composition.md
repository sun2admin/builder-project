# build-workflow Stack Composition Plan

**Skill path:** `.claude/skills/build-workspace/build-workspace.sh`
**Status:** Active — composition responsibilities being lifted out of `analyze-project`

> **Architectural directive (2026-05-05):** `analyze-project` is a pure
> detector. It scans one repo and emits raw facts. **All stack composition
> logic belongs in `build-workflow` (this skill).** When `build-workflow`
> walks user prompts, it invokes `analyze-project` once per repo (project
> repo + each selected plugin repo), aggregates the resulting analyses, and
> composes the layer stack.

> **REQUIRED READING before changes:**
> - Stack architecture → `../../CLAUDE.md` (Architecture section)
> - Layer 4 split → [`layer4-design.md`](./layer4-design.md)
> - Analyze-project schema → [`../skills/analyze-project/DATA_SCHEMA.md`](../skills/analyze-project/DATA_SCHEMA.md)
> - Detection principles (parallel separation rule applies) → [`../skills/analyze-project/DETECTION_PRINCIPLES.md`](../skills/analyze-project/DETECTION_PRINCIPLES.md)

---

## Boundary

### What stays in analyze-project (pure detection)
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

### What moves to build-workflow (composition / opinion)
- `suggested.base_image` — picks L1 variant
- `suggested.dockerfile_from` — project-native runtime image (compositional hint)
- `suggested.ai_install` — picks L2 variant
- `suggested.plugin_layer` — picks L3 image
- `firewall_required` (bool) — derived flag composing capabilities + script presence
- All composition fields proposed in earlier sessions but NOT added to the
  skill: `extras_needed`, `devcontainer_features`, `version_overlays`,
  `L1_LATEST_RUNTIMES`, `DEVCONTAINER_FEATURE_MAP`

---

## Stack-composition responsibilities

### 1. Multi-repo analysis aggregation

`build-workflow` invokes `analyze-project` on multiple repos:

```
analyses = []
analyses.append(analyze_project(<project repo>))
for plugin_repo in selected_plugins_from_menu:
    analyses.append(analyze_project(plugin_repo))
```

Each call writes to `builds/<owner>/<repo>/analysis.json`. build-workflow
reads each, merges by category. Merge rules:

| Field | Merge rule |
|---|---|
| Sets (languages, system_packages, env_vars, claude_plugins, browser_tools) | Union, then sort |
| Per-language libs | Union per-lang, then sort |
| Domains | Union, then sort |
| Credentials | Union per-bucket (api_keys/tokens/other), `ssh = any(ssh)` |
| MCP servers | Union by `name` field; conflict on duplicate name → prompt user |
| post_start chains | Concatenate in order: project chain first, then plugin chains |
| init_scripts | Union, preserve order |
| runtime_versions | Conflict-resolve: prefer pinned over latest, prompt user on cross-repo conflict |
| capabilities, volumes | Union; volumes deduped by `target` path |

### 2. L1 variant selection — minimal viable + user override

Pick the **smallest L1 variant that covers all aggregated dependencies**,
then offer user the option to override upward (never downward).

**Capability profile of each L1 variant** (source of truth, lives in
`build-workflow`, versioned in lockstep with L1 image publish):

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
    'playwright_with_firefox':  { 'rank': 3, 'provides': {..., 'firefox'},  ... },
    'playwright_with_safari':   { 'rank': 3, 'provides': {..., 'webkit'},   ... },
    'playwright_with_all':      { 'rank': 4, 'provides': {..., 'chromium', 'firefox', 'webkit'}, ... },
}
```

**Required capabilities derived from aggregated analysis:**

```python
def required_caps(agg):
    caps = {'node', 'shell'}                             # always required
    if 'python' in agg['languages']:        caps.add('python')
    if 'playwright' in agg['browser_tools']:caps.add('playwright-core')
    # browser flavor from playwright config / source patterns
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
    # Filter to variants that satisfy needed; pick lowest rank
    candidates = [
        (name, v) for name, v in L1_VARIANTS.items()
        if needed <= v['provides']
    ]
    if not candidates:
        # No existing variant covers all deps — fall back to playwright_with_all
        # OR prompt user about adding deps via L4 features
        return None  # caller handles
    auto_pick = min(candidates, key=lambda x: x[1]['rank'])
    return auto_pick[0]
```

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

**Interactive flow:**

```
analyze-project completes for project + N plugin repos
   ↓
aggregate analyses
   ↓
required = required_caps(aggregated)
auto_pick = pick_l1(aggregated)        # e.g., 'light' if no python/playwright

Print:
  "Required L1 capabilities: {required}"
  "Minimal variant: {auto_pick}"
  "Higher-capability options: [latest, playwright_with_chromium, ...]"
  "Press ENTER to accept, or pick override:"
   ↓
if user_input:
    valid, err = validate_override(user_input, required)
    if not valid: REJECT, re-prompt
   ↓
final_l1 = user_input or auto_pick
```

**Examples:**

| Project | required_caps | auto_pick | Allowed overrides |
|---|---|---|---|
| Pure node CLI tool | `{node, shell}` | `light` | `latest`, all `playwright_with_*` |
| Node + Python AI app | `{node, shell, python}` | `latest` | All `playwright_with_*` |
| Node + Python + Playwright (Chromium) | `{node, shell, python, playwright-core, chromium}` | `playwright_with_chromium` | `playwright_with_all` |
| Node + Python + Playwright (multi-browser) | `{..., chromium, firefox, webkit}` | `playwright_with_all` | (no higher option) |

**Rejection example:**
- auto_pick = `latest` (project needs python)
- user tries override `light`
- validate fails: missing `{python}`
- workflow re-prompts: "`light` doesn't ship Python; pick from {latest, playwright_with_*}"

**Why minimal-viable over always-:latest:**
- Smaller image pull (`:light` ~150MB vs `:latest` ~600MB)
- Faster cold start on first dev build
- Less disk usage per dev workstation
- User can override upward if they want bigger toolchain (e.g., dev wants
  `:latest` even on a node-only project to have Python available for
  ad-hoc scripts)

**Why never override downward:**
- Validate refuses overrides that drop required capabilities
- Prevents broken devcontainers from manual misconfiguration
- Auto-pick is the floor; override is opt-up only

### 3. L2 variant selection
Default: `claude`. Override: explicit user prompt `"Which AI CLI?"`.

### 4. L3 plugin layer selection
- Take `aggregated.claude_plugins` (union from project + plugin repos)
- Query GHCR for `claude-plugins-*` images that contain ALL required plugins
- If exact match: use it
- If subset match: pick smallest superset
- If no match: invoke `/new-plugin-layer` to build new image with the union
- Prompt user before triggering new builds

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

These constants live in `build-workflow` and update when L1 image content
changes — single source of truth, versioned in lockstep with L1 publish.

### 6. Credentials wiring
- For each entry in `aggregated.credentials_required`, decide whether to use
  `containerEnv` passthrough (host env) or `/run/credentials/<name>` mount
- Prompt user once per cred for delivery method
- Generate appropriate devcontainer.json `containerEnv` and `mounts`

### 7. Firewall composition
- Set `runArgs` `--cap-add NET_ADMIN/NET_RAW` if any aggregated analysis
  shows iptables-touching init script OR explicit capability
- Generate per-project firewall extension if `aggregated.external_services.domains`
  exceeds L1's baked allowlist (write extra-domains script invoked after
  L1's init-firewall.sh)

### 8. Init script chain assembly
- Concatenate per-repo chains in order (project first, plugins after)
- Deduplicate by script path
- Handle ordering constraints (firewall before SSH before token; user-prompt
  if conflicting orders detected)
- Emit final `postStartCommand` string

---

## Decision-rule summary (heavy asset vs feature)

Composition logic (lives in build-workflow, NOT in skill):

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

When a feature becomes ubiquitous:
1. Track feature usage frequency across all `builds/*/analysis.json` runs
2. When >50% of recent projects use feature X → propose promotion
3. Stack maintainer approves; bumps L1 image with X baked in
4. `build-workflow` constants updated; X removed from `DEVCONTAINER_FEATURE_MAP`
5. Existing devcontainer.json files using the feature continue to work
   (feature install becomes idempotent — already-installed = noop)

---

## Migration steps from current state

1. **Remove `suggested` block from `analyze-project`** — clean break.
   Update `analyze-project.sh` to drop the `suggested` JSON field and the
   "Suggested Stack" markdown table. Update `DATA_SCHEMA.md` to remove the
   `suggested.*` rows. Plan Gap entries reference deprecation date.

2. **Remove `firewall_required` from analyze-project** — keep raw signals
   (`container.capabilities`, `init_scripts` with iptables content). Build-
   workflow derives the bool from raw signals.

3. **Implement composition in build-workflow:**
   - Read `analyses[]` from `builds/<owner>/<repo>/analysis.json`
   - Aggregate per merge rules above
   - Apply L1/L2/L3 selection logic
   - Apply L4 feature/overlay logic
   - Generate final devcontainer.json
   - Emit summary to user

4. **Schema-stability bump** — composition fields removal is breaking. If any
   downstream consumers exist that read `suggested.*` directly, update them
   in lockstep (search builder-project for consumers before removal).

5. **Update reference docs:**
   - `DATA_SCHEMA.md` → mark `suggested.*` and `firewall_required` removed,
     add deprecation note
   - `DETECTION_PRINCIPLES.md` → add boundary rule: skill never composes
   - `TESTING.md` → update test corpus expectations (no `suggested` field)

---

## Composition Doctrine

Three rules for analyze-project / build-workflow boundary:

1. **Detection ≠ provisioning** — skill detects what a repo declares;
   build-workflow decides what to install where.
2. **Skill emits raw signals; workflow makes decisions.** If a field in
   `analysis.json` is computed from other fields plus opinion, it belongs
   in build-workflow.
3. **Test the boundary** — every analyze-project test should pass without
   any compositional output. If a test breaks, the skill is doing too much.

---

## Open Questions

- Should the multi-repo analysis aggregation produce a separate
  `builds/<workspace-name>/aggregated.json` artifact, or compute on-the-fly?
- How to handle conflicting `runtime_versions` across project + plugins
  (e.g., project pins node 18, plugin pins node 22)?
- Plugin repo discovery: how does build-workflow obtain a plugin's source
  repo URL from its GHCR image name? Currently the relationship is implicit.
