# analyze-repo — Data Schema & Layout

**Read this when modifying output structure, the analyzed_repos cache, or
`tool-deps.json`.** Sibling to `DETECTION_PRINCIPLES.md`. Companion files
serve different concerns:

- `DETECTION_PRINCIPLES.md` — HOW detection is coded (rules, regex idioms)
- `DATA_SCHEMA.md` (this file) — WHAT the skill writes (paths, JSON shape, cache, consumer contract)
- `TESTING.md` — HOW to verify changes (test corpus, regression protocol)
- `SKILL.md` — WHEN the skill triggers (description, brief usage)
- `.claude/plans/analyze-repo-skill.md` — active dev plan + gap tracking

If a change here affects detection logic, update both files. If a change
breaks downstream consumers (`/build-stack` skill + tool), bump the schema
version and document the migration.

---

## Directory Layout

### Skill directory
```
.claude/skills/analyze-repo/
├── SKILL.md                  ← discovery / triggering
├── analyze-repo.sh           ← orchestrator (bash + inline Python)
├── DETECTION_PRINCIPLES.md   ← detection rules (load on edit)
└── DATA_SCHEMA.md            ← this file (load on schema work)
```

### Tool data directory
```
tools/build-stack/build_stack/data/
└── tool-deps.json            ← cached tool→apt mappings (committed)
```

The `tool-deps.json` cache lives with the build-stack tool (not the
analyze-repo skill) because it is consumed by the Python implementation
in `tools/build-stack/build_stack/analyzers/`. Post-Phase-3 cutover
(commit `404950e`), the analyze-repo skill is a 59-line bash wrapper
that execs `python -m build_stack analyze`, so the cache has a single
canonical owner.

### Output directory (analyzed_repos cache)
Output lives **outside** the skill at the repo root:
```
analyzed_repos/
└── <owner>/
    └── <repo>/
        ├── analysis.json     ← machine-readable, consumed by /build-stack
        └── analysis.md       ← human-readable summary
```

**Two-level structure** (`<owner>/<repo>/`) mirrors GitHub's namespace.
Avoids flat-list confusion when multiple owners share repo names.

**Why a separate top-level dir** (vs `builds/`): `analyzed_repos/` is a
content-addressed cache keyed on real GitHub coordinates and reusable
across multiple builds. `builds/` is user-organized
(`builds/<category>/<project>/`) and holds composed stack outputs. Keeping
them split prevents a build dir from shadowing the cache or vice versa.

**Navigation flow for resuming an analysis** (used by `/build-stack`):
1. `ls analyzed_repos/` → owner menu
2. User picks owner → `ls analyzed_repos/<owner>/` → repo menu
3. User picks repo → load `analyzed_repos/<owner>/<repo>/analysis.json`

**Git policy:**
- `analyzed_repos/` itself **is** committed (intentional artifact history for diff/audit)
- Generated cruft inside (clones, tmp) is `.gitignore`d
- Only `analysis.json` and `analysis.md` are committed per repo

---

## analysis.json Schema

Top-level keys (current):

| Key | Type | Source/Meaning |
|---|---|---|
| `repo` | string | `owner/repo` GitHub identifier |
| `project` | string | repo name only |
| `analyzed_at` | string | `YYYY-MM-DD` |
| `purpose` | string | derived from README first paragraph |
| `primary_language` | string | dominant lang from manifest detection |
| `languages` | string[] | all detected lang slugs (lowercased) |
| `runtime_extras` | string[] | extras like `playwright`, `cuda` |
| `runtime_versions` | object | `{lang: version}` from manifests |
| `dockerfile_base` | string | `FROM` value (literal, including `${VAR}`) |
| `system_packages` | string[] | apt/apk packages from RUN install |
| `extra_binaries` | string[] | curl/wget release-download artifacts |
| `global_js_packages` | string[] | JS package-manager global installs from Dockerfile (npm/pnpm/yarn/bun) |
| `dockerfile_python_installs` | string[] | `pip install` / `pip3 install` / `pipx install` packages from Dockerfile RUN blocks (skips `-r requirements.txt`) |
| `dockerfile_go_installs` | string[] | `go install <module-path>@<version>` invocations from Dockerfile RUN blocks |
| `libraries` | object | `{node[], python[], go[], rust[]}` |
| `ports.inbound` | int[] | EXPOSE + docker-compose ports + source patterns |
| `external_services` | object | `{domains[], source}` — `source` = origin classification |
| `env_vars` | string[] | from .env.example, Dockerfile ENV, compose `environment` |
| `browser_tools` | string[] | playwright/puppeteer/selenium/cypress signals |
| `github_api_usage` | bool | @octokit / PyGithub / go-github / Octokit |
| `container` | object | `{capabilities[], volumes[], env{}, remote_user, post_start, post_create, post_start_chain[], post_create_chain[], init_scripts[], extensions[]}` |
| `container.post_start_chain` | object[] | per-step decomposition of `post_start` (`{raw, sudo, script, args, in_repo}`) |
| `container.post_create_chain` | object[] | same shape for `post_create` |
| `container.init_scripts` | string[] | unique repo-relative paths of in-repo scripts referenced by either chain |
| `credentials_required` | object | `{api_keys[], tokens[], ssh:bool, other[]}` — populated from env vars (suffix routing) AND from `/run/credentials/*` bind-mount targets in `container.volumes` (filename → suffix routing; SSH key shapes set `ssh:true`) |
| `mcp_servers` | object[] | from `.mcp.json` |
| `claude_plugins` | string[] | from `.claude/plugins.json` |
| `inferred` | object | `{tools[], tools_new[], tools_confirmed[], py_imports[], ts_imports[], ci_tools[]}` |
| `system_deps` | object | `{tool: {apt_package, apt_depends[]}}` resolved via `tool-deps.json` |
| `schema_version` | int | Current: `2`. Bumped when fields removed/renamed. |

### Field semantics

- **`inferred.tools`** — full set of commands detected in source (high noise)
- **`inferred.tools_new`** — `tools` minus anything covered by `system_packages`
  (the actionable subset)
- **`inferred.tools_confirmed`** — `tools` already declared explicitly in Dockerfile
- **`inferred.ts_imports_new`** — `ts_imports` minus `libraries.node`
  (TS/JS imports not yet declared in package.json)
- **`inferred.ts_imports_confirmed`** — `ts_imports` already in package.json
- **`inferred.py_imports_new`** / **`py_imports_confirmed`** — same dedup vs `libraries.python`
- **`system_deps`** — only entries where apt-cache resolved `apt_package != null`
  reach this field (the noise filter)
- **`external_services.source`** — one of: `firewall_script`, `source_scan`,
  `config_files`, `readme_codefence`, `readme_prose`, `multi`. Use this to
  judge confidence downstream.

### Adding a new field
Checklist:
1. Add to bash export (`export AR_FOO="$FOO_JSON"`)
2. Add to Python data dict using `e()` / `s()` / `b()` helper
3. Add markdown rendering section
4. Update this schema table
5. Update `analyze-repo-skill.md` JSON Schema example
6. Tell `/build-stack` if it should consume the new field (and add a row to the Consumer Contract table below)

---

## tool-deps.json Schema

Path: `tools/build-stack/build_stack/data/tool-deps.json`
Initial state: `{}`. Grows incrementally; committed to version control.

```json
{
  "<tool-name>": {
    "apt_package": "<debian-package-name>" | null,
    "apt_depends": ["<dep1>", "<dep2>", ...]
  }
}
```

**Population:**
- Skill calls `apt-cache search <tool>` + `apt-cache show <pkg>` at runtime
  the first time it sees a tool name
- Result cached forever (until manual purge)
- `apt_package: null` means the tool name has no Debian package — these
  remain in the cache to avoid re-querying, and are filtered out before
  reaching `system_deps` in the output

**Write semantics:**
- File is rewritten only when new entries were added (`cache_updated` flag)
- Never edited manually — let the skill populate it

**Size considerations:**
- Currently ~600 entries; grows to maybe a few thousand long-term
- Plain JSON object — keep flat, no nesting changes without a migration

---

## Consumer Contract

Each `analysis.json` field is consumed by the `/build-stack` tool. Section
references point into [`build-workflow-stack-composition.md`](../../../.claude/plans/build-workflow-stack-composition.md)
where the per-field merge rule and composition decision is specified.
The plan is the durable contract; tool source modules (`select.py`,
`compose.py`, `aggregate.py`, `emit.py`) implement it but may refactor.

| `analysis.json` field | Consumer | How it's used |
|---|---|---|
| `system_packages`, `inferred.tools_new`, `inferred.ci_tools`, `system_deps`, `global_js_packages` | `/build-stack` tool — §2 | L1 capability cover input; falls through to §5 L4 install when a needed capability is not bakeable into any L1 variant |
| `libraries.rust` | `/build-stack` tool — §1 | Aggregated for cross-repo merge; informational signal in `aggregated.json` |
| `external_services.domains` | `/build-stack` tool — §7 | Firewall extension diff vs L1 `init-firewall.sh` allowlist; emit `extra-domains.sh` when diff non-empty |
| `claude_plugins` | `/build-stack` tool — §4 | L3 plugin layer pick (set-cover with monotone preference); falls through to recommended-L3 + features hybrid per parent plan amendment |
| `mcp_servers` | `/build-stack` tool — §1 | Aggregation merge: union by `name`; conflict on duplicate name fails the build |
| `credentials_required` | `/build-stack` tool — §6 | Credentials wiring: `containerEnv` passthrough (default) or `/run/credentials/<name>` mount per per-cred override |
| `container.capabilities` | `/build-stack` tool — §7 | `runArgs --cap-add NET_ADMIN/NET_RAW` derivation when iptables-touching init scripts present |
| `container.volumes` | `/build-stack` tool — §5 | Devcontainer `mounts` (deduped by `target` path during aggregation per §1) |
| `container.env` | `/build-stack` tool — §5 | Devcontainer `containerEnv` |
| `container.post_start`, `container.post_start_chain`, `container.init_scripts` | `/build-stack` tool — §8 | Init script chain assembly under partial order constraints (firewall first, `load-projects.sh` last); emits final `postStartCommand` |
| `container.extensions` | `/build-stack` tool — §5 | Devcontainer VS Code extensions |
| `ports.inbound` | `/build-stack` tool — §5 | Devcontainer `forwardPorts` |

## Schema Stability

**Breaking changes** (renames, removed fields, type changes) require:
1. Bump `schema_version` field (add it if not present yet)
2. Update every consumer in lockstep
3. Document migration in plan file's gap section

**Non-breaking changes** (add new field, fill optional value):
- Just add. Consumers that don't know the field ignore it.
