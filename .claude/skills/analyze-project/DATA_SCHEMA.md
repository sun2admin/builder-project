# analyze-project — Data Schema & Layout

**Read this when modifying output structure, the builds registry, or
`tool-deps.json`.** Sibling to `DETECTION_PRINCIPLES.md`. Companion files
serve different concerns:

- `DETECTION_PRINCIPLES.md` — HOW detection is coded (rules, regex idioms)
- `DATA_SCHEMA.md` (this file) — WHAT the skill writes (paths, JSON shape, cache, consumer contract)
- `TESTING.md` — HOW to verify changes (test corpus, regression protocol)
- `SKILL.md` — WHEN the skill triggers (description, brief usage)
- `.claude/plans/analyze-project-skill.md` — active dev plan + gap tracking

If a change here affects detection logic, update both files. If a change
breaks downstream consumers (`build-workspace`), bump the schema version
and document the migration.

---

## Directory Layout

### Skill directory
```
.claude/skills/analyze-project/
├── SKILL.md                  ← discovery / triggering
├── analyze-project.sh        ← orchestrator (bash + inline Python)
├── tool-deps.json            ← cached tool→apt mappings (committed)
├── DETECTION_PRINCIPLES.md   ← detection rules (load on edit)
└── DATA_SCHEMA.md            ← this file (load on schema work)
```

### Output directory (builds registry)
Output lives **outside** the skill at the repo root:
```
builds/
└── <owner>/
    └── <repo>/
        ├── analysis.json     ← machine-readable, consumed by build-workspace
        └── analysis.md       ← human-readable summary
```

**Two-level structure** (`<owner>/<repo>/`) mirrors GitHub's namespace.
Avoids flat-list confusion when multiple owners share repo names.

**Navigation flow for resuming an analysis** (used by `build-workspace`):
1. `ls builds/` → owner menu
2. User picks owner → `ls builds/<owner>/` → repo menu
3. User picks repo → load `builds/<owner>/<repo>/analysis.json`

**Git policy:**
- `builds/` itself **is** committed (intentional artifact history for diff/audit)
- Generated cruft inside builds (clones, tmp) is `.gitignore`d
- Only `analysis.json` and `analysis.md` are committed per build

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
1. Add to bash export (`export AP_FOO="$FOO_JSON"`)
2. Add to Python data dict using `e()` / `s()` / `b()` helper
3. Add markdown rendering section
4. Update this schema table
5. Update `analyze-project-skill.md` JSON Schema example
6. Tell `build-workspace` if it should consume the new field

---

## tool-deps.json Schema

Path: `.claude/skills/analyze-project/tool-deps.json`
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

Each `analysis.json` field maps to a specific layer skill output target:

| `analysis.json` field | Consumer | How it's used |
|---|---|---|
| `system_packages` + `inferred.tools_new` | `build-layer1` Dockerfile | apt-get packages to add |
| `system_deps` | `build-layer1` Dockerfile | Resolved apt packages for inferred tools |
| `global_js_packages` | `build-layer1` Dockerfile | JS pkg-manager globals (npm/pnpm/yarn/bun) to add |
| `external_services.domains` | `build-layer1` `init-firewall.sh` | Allowlist domains |
| `libraries.rust` | `build-layer1` Dockerfile | Rust crate deps for build cache |
| `inferred.ci_tools` | `build-layer1` Dockerfile | Additional tools revealed by CI config |
| `container.capabilities` | `build-layer4` devcontainer.json `runArgs` | `--cap-add` flags |
| `container.volumes` | `build-layer4` devcontainer.json `mounts` | Named volumes + credential mounts |
| `container.env` | `build-layer4` devcontainer.json `containerEnv` | Env var passthroughs |
| `container.post_start` | `build-layer4` devcontainer.json | `postStartCommand` (raw string, back-compat) |
| `container.post_start_chain` | `build-layer4` | per-step init script enumeration; pick scripts to bundle into devcontainer |
| `container.init_scripts` | `build-layer4` | list of in-repo scripts to include in workspace `.devcontainer/scripts/` |
| `container.extensions` | `build-layer4` devcontainer.json | VS Code extensions |
| `credentials_required` | `build-layer4` init scripts | Determine which init-*.sh are needed |
| `mcp_servers` | `build-layer4` `.mcp.json` | MCP server config |
| `ports.inbound` | `build-layer4` devcontainer.json `forwardPorts` | Port forwarding |
| `claude_plugins` | `build-layer3` | Plugin layer selection signal |

## Schema Stability

**Breaking changes** (renames, removed fields, type changes) require:
1. Bump `schema_version` field (add it if not present yet)
2. Update every consumer in lockstep
3. Document migration in plan file's gap section

**Non-breaking changes** (add new field, fill optional value):
- Just add. Consumers that don't know the field ignore it.
