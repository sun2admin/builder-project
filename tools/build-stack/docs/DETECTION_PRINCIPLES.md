# analyze-repo — Detection Principles

**Read this before modifying the skill's detection logic.** Every category
(packages, libraries, binaries, tools, domains, env vars, credentials) follows
the same rule: **derive from the artifact, never compare against an opinion
list.**

**Companion docs:**
- [`DATA_SCHEMA.md`](./DATA_SCHEMA.md) — output JSON shape, builds dir layout,
  tool-deps.json schema, consumer contract. Read when changing what the skill writes.
- [`TESTING.md`](./TESTING.md) — test repo corpus, regression protocol, noise floor.
  Read when validating fixes.
- [`SKILL.md`](./SKILL.md) — discovery / triggering description.
- [`../../plans/analyze-repo-skill.md`](../../plans/analyze-repo-skill.md)
  — active dev plan + gap tracking.

## Core Principle

The skill discovers what a repo declares. It does **not** carry an opinion
about what tools/packages/services exist in the world. Hardcoded filter lists
(`KNOWN_TOOLS`, `STDLIB_PY`, `COMMON_DOMAINS`, etc.) grow forever, miss novel
cases, and encode knowledge that belongs in the repo being analyzed.

## Composition Boundary (post-schema-v2)

**Detection ≠ provisioning.** This skill emits raw signals about what a repo
declares. It does NOT emit composed/derived/opinionated values about how to
provision a stack. Composition belongs to `/build-stack` (skill + tool).

**Forbidden in this skill:**
- Image-variant selection (`suggested.base_image`, `suggested.dockerfile_from`)
- AI CLI selection (`suggested.ai_install`)
- Plugin layer selection (`suggested.plugin_layer`)
- Derived bool flags computed from other fields (`firewall_required`)
- "What features should the project devcontainer install" decisions

**If a proposed field would be computed by combining other fields with
opinion/preference, it belongs in `/build-stack`.** Push back, route the
change to [`build-workflow-stack-composition.md`](../../../.claude/plans/build-workflow-stack-composition.md) instead.

**Test the boundary:** every analyze-repo test should pass without any
compositional output. If a test would break without `suggested.*`, the test
is testing the wrong skill.

If a detector needs to know "is X a real thing?", the answer comes from a
runtime query (apt-cache, `sys.stdlib_module_names`, `node -e
"require('module').builtinModules"`) or a cached lookup file
(`tool-deps.json`) — never an inline list.

---

## Per-Category Rules

### System Packages
- Source: `RUN apt-get install`, `apt install`, `apk add` lines in Dockerfile
- Extract: tokens after `install`/`add`, stop at `&&` or `;`
- Filter: regex shape `^[a-z][a-z0-9._+-]{1,}$` (Debian/Alpine pkg name shape)
- **Never** carry a list of "known" packages — emit whatever appears.

### Libraries (language-level deps)
- Source: language manifests (`package.json`, `requirements.txt`, `pyproject.toml`,
  `Pipfile`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`, `pom.xml`,
  `build.gradle`)
- Extract directly from the manifest's declared schema
- Schema-defined keys (`dependencies`, `devDependencies`, `require`, `[dependencies]`)
  are **legitimate hardcoding** — they are part of the manifest spec, not opinion

### Global Binary Installs (Dockerfile)
- **Multi-package-manager coverage required:** `npm install -g`, `npm i -g`,
  `yarn global add`, `pnpm add -g`, `pnpm install -g`, `bun install -g`,
  `bun add -g`, `pip install`, `pipx install`, `go install <pkg>@<ver>`,
  `cargo install`, `gem install`
- Use `re.finditer` (not `re.search`) — `if/else` shell blocks put multiple
  installs on a single joined line
- Pattern shape: `<tool> <subcmd> -g (.*?)(?:&&|\|\||;|$)` with non-greedy
  body and explicit terminator
- Strip flags via `tok.startswith('-')` — never enumerate known flags
  (`--silent`, `--unsafe-perm`, etc.)
- Preserve version pins (`typescript@5.4`, `tool@v1.2.3`) — useful signal

### Binary Downloads (curl/wget)
- Pattern: `releases/download/<tag>/<artifact>` from GitHub release URLs
- Extract artifact name only — version comes from tag if needed

### Tools / Commands (inferred from source)
- Source: shell scripts, GitHub Actions `run:` blocks, Makefile recipes,
  Dockerfile RUN
- Extraction:
  - Get bash builtins/keywords at runtime: `compgen -b; compgen -k`
  - Extract first token after delimiters (`;`, `|`, `&&`, `||`, `(`, `{`, newline)
  - Detect explicit dependency markers: `command -v X`, `which X`, `type X`
  - Detect shebangs: `#!/usr/bin/env X`
  - For CI `uses:` action names: strip `setup-`/`install-` prefixes and
    `-action`/`-toolchain`/`-cache` suffixes to derive tool name dynamically
- **Never** maintain a `KNOWN_TOOLS` list

### Python stdlib
- Use `sys.stdlib_module_names` (Python 3.10+)
- Fallback: `pkgutil.iter_modules([stdlib_path])`
- Never inline a list

### Node stdlib
- Query at runtime: `node -e "console.log(require('module').builtinModules.join('\n'))"`
- Never inline a list

### Domains / External Services
- Classify by **where** the URL appears, not **what** the domain is:
  - Source HTTP calls (`fetch`, `requests.get`, `curl`, `http.Get`) → high
  - Config/env files (`.env.example`, `docker-compose.yml`) → high
  - Firewall scripts → confirmed
  - README code fences → medium
  - README service-keyword prose → medium
  - README badge lines (`[![...](...)](...)`) → skip (not runtime)
- **No domain blocklist.** Only always-skip: localhost, `127.*`, `0.0.0.0`

### Credentials Required
- Routing by env-var name suffix: `_KEY$`, `_SECRET$`, `_TOKEN$`, `_PAT$`
- These are **industry naming conventions**, not opinion lists — legitimate
- Cross-reference bind mounts under `/run/credentials/*` as auth signals

### tool-deps.json
- Lives alongside the skill — caches `tool → apt_package` mappings discovered
  via `apt-cache show`
- Read+write at runtime; avoids re-querying apt
- Tools resolving to `apt_package: null` stay in `inferred.tools` as visual
  noise but never reach actionable `system_deps`

---

## Acceptable Hardcoding (Not a Violation)

Hardcoding is permitted when the value is part of an **external schema** or
**universal constant**, not an opinion about the world:

| Hardcoded | Reason |
|---|---|
| Cargo `[dependencies]`/`[dev-dependencies]` section names | Cargo's published TOML schema |
| Credential suffix regex (`_KEY$`/`_SECRET$`/`_TOKEN$`/`_PAT$`) | Industry naming convention |
| Localhost / `127.*` / `0.0.0.0` skip | Always-true network addresses |
| Shell delimiters (`;`, `\|\|`, `&&`, `\|`, `(`, `{`) | POSIX shell grammar |
| Debian/Alpine pkg name regex (`^[a-z][a-z0-9._+-]{1,}$`) | Distro spec |
| `FROM` / `RUN` / `ENV` / `EXPOSE` keyword detection | Dockerfile spec |

If a new hardcode doesn't fit one of these categories, find the dynamic
alternative.

---

## Implementation Patterns

### Multi-occurrence on one joined line
Use `re.finditer` with non-greedy `(.*?)` + terminator `(?:&&|\|\||;|$)`.
`re.search` only finds the first match — fails on shell `if/else` blocks
where both branches end up on one continuation-joined line.

### Backslash continuation
Always join continuation lines before regex scanning:
```python
joined = []
buf = ""
for line in lines:
    s = line.rstrip()
    if s.endswith("\\"):
        buf += s[:-1] + " "
    else:
        buf += s
        joined.append(buf)
        buf = ""
```

### Token filtering
Filter by **shape**, not **identity**:
- Flags: `tok.startswith('-')`
- Shell ops: `tok in ('|', '||', '&&', ';')`
- Pkg names: regex shape match
- Never: `if tok in KNOWN_LIST`

### Noise reduction (verified against gstack)
- **No dots in `DELIMITERS_RE`** — Linux commands never contain dots; allowing
  them matches `JSON.parse`, `j.category`, Go method calls, Python attributes
- **Uppercase-first filter** (`not cmd[0].isupper()`) — eliminates Python class
  names, TS interfaces, proper nouns. (`cmd.isupper()` alone only catches
  ALL-CAPS constants.)
- **Makefile recipe-only filter** — only TAB-indented lines are shell;
  column-0 lines are target labels
- **GitHub Actions `${{ }}` stripping** — strip context expressions before
  regex extraction; they look like dotted command tokens
- **Inline interpreter script stripping** — strip
  `(node|bun|deno|python3?|ruby|perl) -e "..."` before CI command extraction;
  inline JS/Python keywords are not shell tools
- **`len(cmd) > 1`** guard on `command -v`/`which`/`type` matches

---

## Bash / Python / Grep Idioms

Hard-won engineering patterns. Each one fixes a class of bug, not a single
incident — apply consistently.

### Env-var bridge: bash → Python
All bash-collected data is exported as `AR_*` env vars before a single
`python3 << 'PYEOF'` block reads them and serializes JSON.
- **Single-quoted heredoc** (`<< 'PYEOF'`, not `<< PYEOF`) prevents bash from
  expanding `${}` inside Python — critical because Python uses `{}` for
  f-strings.
- **Export timing matters:** any `AR_*` var must be exported BEFORE the
  Python block that reads it. `AR_NODE_BUILTINS` (set after `node -e`) must
  be exported before the inferred-source Python block, not in the main
  exports section near the bottom.

### pipefail + grep exit-1 trap
`set -euo pipefail` makes any failing pipeline command abort the script.
`grep` exits 1 when no matches found — even a clean run.

**Fix:** wrap grep in `{ grep ... || true; }` in any pipeline that feeds
JSON serialization. Without this, Python prints valid JSON, then a fallback
`|| echo "[]"` appends another `[]`, producing `[]\n[]` — fails
`json.loads()`.

### Markdown table conditional rows
Embedding conditional rows in an f-string triple-quote breaks the table:
```python
# WRONG — empty line when condition false splits table in two
f"""| row1 |
{f'| optional |' if condition else ''}
| row2 |"""
```
**Fix:** build rows as a list, join at the end:
```python
rows = ["| row1 |"]
if condition: rows.append("| optional |")
rows.append("| row2 |")
md += "| Header |\n|---|\n" + "\n".join(rows)
```

### Python for parsing, bash for orchestration
- **Bash:** clone, file discovery, loop iteration, env var setup, find/grep
- **Python:** JSON generation, JSONC parsing, Dockerfile parsing, regex extraction
- **Never mix:** generating JSON in bash by string concatenation is forbidden;
  `echo "$VAR" | python3 -c "..."` is the bridge.

### find / grep exclusions
Always exclude `.git` and dependency trees:
```bash
find . -not -path "./.git/*" -not -path "*/node_modules/*" \
       -not -path "*/vendor/*" -not -path "*/.venv/*" \
       -not -path "*/__pycache__/*"
```
`grep -v ".git"` is **insufficient** — paths with `.git` as a directory
component slip through.

For URL/SSH/source scans, also exclude **lock files by name**:
`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`,
`Gemfile.lock`, `composer.lock`. Lock files contain transitive metadata
(author URLs, funding links, `git+ssh://` repo URLs) — install-time noise,
not runtime deps. Without this, a shallow npm clone floods the URL list
with hundreds of author homepages.

### Variable-length lookbehind in grep
GNU grep PCRE (`-P`) does **not** support variable-length lookbehinds like
`(?<=releases/download/[^/]+/)`. Use `\K` instead — it resets match start
and has no fixed-length restriction:
```
grep -oP 'releases/download/[^/]+/\K[^\s"\'"]+'
```

### README parsing pitfalls
Three bugs caught the hard way; all three guards required.

1. **Inline HTML strip:** Modern READMEs use `<strong>`, `<em>`, `<br>`
   inside paragraph text. After stripping markdown syntax, run
   `re.sub(r'<[^>]+>', '', line)`. Lines starting with `<` are skipped as
   block-level HTML, but inline tags within paragraphs need explicit removal.

2. **Blockquote skip:** Lines starting with `>` are blockquote callouts
   ("repo is being reorganized", "deprecated"), not project descriptions.
   Add `>` to the skip set:
   `startswith(('#', '!', '<', '|', '[', '>'))`.

3. **Short-snippet fallback:** READMEs in transition may have a real first
   paragraph that's a dialogue fragment or notice (<80 chars). The 30-char
   minimum alone won't catch these. After extracting README purpose:
   `[[ ( -z "$PURPOSE" || ${#PURPOSE} -lt 80 ) && -n "$REPO_DESC" ]]` →
   prefer GitHub API description; it's intentionally a project summary.

---

## When Adding a New Detector

Checklist:

1. **Source artifact** — what file/section declares this category?
2. **Schema spec** — does the artifact have a published format? Use it.
3. **Runtime query** — if filtering needed, what command/API gives the truth
   at runtime (apt-cache, stdlib_module_names, builtinModules)?
4. **Cache** — if the runtime query is expensive, cache it in a JSON file
   alongside the skill
5. **Multi-variant coverage** — if it's a tool family (npm/yarn/pnpm/bun, or
   pip/pipx, or go/cargo/gem), cover the family, not one member
6. **Audit** — list every constant in the new code. Each one must map to the
   "Acceptable Hardcoding" table or be replaced.

If step 6 produces an unexplained constant, the detector is wrong. Fix it
before merging.
