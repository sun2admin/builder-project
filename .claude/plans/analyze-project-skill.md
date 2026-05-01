# analyze-project Skill Plan

**Skill path:** `.claude/skills/analyze-project/analyze-project.sh`
**Output path:** `builds/<owner>/<repo>/analysis.json` + `builds/<owner>/<repo>/analysis.md`
**Status:** Active development — core working, iterating on coverage

---

## Purpose

Scan any GitHub repo and produce a complete dependency + configuration map
needed to stand up that project inside our 4-layer container stack. The output
feeds directly into `build-workspace` as structured inputs for each layer skill,
and is also human-readable for review.

---

## Architecture Principles

### Dynamic, not hardcoded
The skill never maintains lists of known domains, tools, stdlib modules, or CI
action mappings. Every such classification is determined at runtime by querying
the environment or the repo itself. This keeps the skill accurate for repos we
haven't seen yet and removes the maintenance burden of growing lists.

The one place caching is intentional: `tool-deps.json` (stored alongside the
skill file) memoizes `apt-cache show` results so we don't re-query apt for the
same tool on every run.

### Dual output: JSON (machine) + Markdown (human)
- `analysis.json` — structured, consumed by `build-workspace` layer skills
- `analysis.md` — printed to stdout + saved, for human review
- Both written atomically at end of scan via a single Python block
- Schema is versioned implicitly by field presence; additive changes are safe

### Env-var bridge pattern for bash→Python
All bash-collected data is exported as `AP_*` env vars before a single
`python3 << 'PYEOF'` block that reads them and serializes to JSON.
Single-quoted heredoc (`<< 'PYEOF'`) prevents bash from expanding `${}` inside
the Python code — critical since Python uses `{}` for f-strings.

**Export timing:** `AP_NODE_BUILTINS` must be exported immediately after the
`node -e "..."` call, before the `INFERRED_SOURCE` Python block at line ~715.
`AP_SKILL_DIR` can go in the main exports block since it's only needed in the
output Python block.

### pipefail + grep exit-1 trap
`set -euo pipefail` makes any failing command in a pipeline abort the script.
`grep` exits 1 when no matches found — even on a clean run. Fix: wrap grep
inside `{ grep ... || true; }` in any pipeline that feeds into Python JSON
serialization. Without this, Python prints valid JSON, then `|| echo "[]"` 
appends another `[]`, producing `[]\n[]` which fails `json.loads()`.

### Conditional Markdown table rows must use list-join, not f-string interpolation
Embedding a conditional row inside an f-string triple-quote block:
```python
f"""| row1 |
{f'| optional |' if condition else ''}
| row2 |"""
```
produces an empty line between rows when the condition is false, breaking the
table into two separate tables in all Markdown renderers. Always build table rows
as a list and `"\n".join()` them:
```python
rows = ["| row1 |"]
if condition: rows.append("| optional |")
rows.append("| row2 |")
md += "| Header |\n|---|\n" + "\n".join(rows)
```

### Python for structured file parsing; bash for orchestration
- Bash: clone, file discovery, loop iteration, env var setup
- Python: JSON generation, JSONC parsing, Dockerfile parsing, regex extraction
- Never mix: bash `echo "$VAR" | python3` is fine; generating JSON in bash
  with string concatenation is not.

### Continuation-line Dockerfile parsing
`grep` sees only the first line of a multi-line `RUN` command. The package
list is on backslash-continuation lines. Always use Python to join `\`-continued
lines before extracting packages, base images, or binary downloads.

### find patterns: always exclude .git and dependency trees
Use `-not -path "./.git/*"` in all `find` calls. `grep -v ".git"` is
insufficient when paths contain `.git` as a directory component.

For URL scans, SSH detection, and all broad `grep -r` calls also exclude:
- **Dependency dirs**: `node_modules/`, `vendor/`, `.venv/`, `__pycache__/`
  — use `--exclude-dir=` flags on grep, or `-not -path "*/node_modules/*"` on find
- **Lock files by name**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`,
  `Cargo.lock`, `Gemfile.lock`, `composer.lock`
  — lock files contain full transitive dependency metadata (author URLs, funding
  links, `git+ssh://` repository URLs) that are install-time noise, not runtime deps

Without this, a shallow clone of any npm project floods the URL list with author
homepages, CDN references, and funding platforms from hundreds of packages.

### Variable-length lookbehind in grep
GNU grep's `-P` (PCRE) does not support variable-length lookbehinds like
`(?<=releases/download/[^/]+/)`. Use `\K` instead — it resets the match
start point and has no fixed-length restriction:
`grep -oP 'releases/download/[^/]+/\K[^\s"\'"]+'`

---

## Detection Categories (current implementation)

### 1. Project Identity
| Signal | Source | Notes |
|---|---|---|
| Purpose | README.md first paragraph | Strip badges, HTML tags, headings, markdown links; take first real paragraph ≥30 chars |
| Purpose fallback | `gh api repos/<owner>/<repo>` `.description` | Used when README has no parseable text |
| Primary language | GitHub API `.language` | Authoritative; language files are unreliable |

**README HTML pitfall:** Modern READMEs use inline HTML (`<strong>`, `<em>`, `<br>`) inside
paragraph text. Strip with `re.sub(r'<[^>]+>', '', line)` AFTER stripping markdown syntax.
Lines starting with `<` are skipped as block-level HTML, but inline tags within text lines
must be stripped explicitly.

**README blockquote pitfall:** Lines starting with `>` are blockquote callouts or notices
("repo is being reorganized", "deprecated", etc.) — not project descriptions. Skip them with
the same `startswith` check used for headings and HTML: `('#', '!', '<', '|', '[', '>')`.

**README short-snippet fallback:** READMEs in transition may have a real first paragraph that's
a dialogue fragment or notice (<80 chars). The 30-char minimum alone won't catch these. Fix:
after extracting README purpose, if it's <80 chars AND `REPO_DESC` (GitHub API description) is
available, prefer `REPO_DESC` — it's intentionally written as a project summary. Full condition:
`[[ ( -z "$PURPOSE" || ${#PURPOSE} -lt 80 ) && -n "$REPO_DESC" ]]`

### 2. Languages & Runtimes
Detected by file presence at repo root:
- `package.json` → node
- `requirements.txt / setup.py / Pipfile / pyproject.toml` → python
- `Gemfile` → ruby, `go.mod` → go, `Cargo.toml` → rust, `pom.xml / build.gradle` → java
- `*.sh` files → shell

Runtime extras (supplement, not replace):
- `bun.lockb / bun.lock` or `#!/usr/bin/env bun` shebang → bun (also implies `node` in languages)
- `deno.json / deno.lock` → deno
- `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn

**File-scan fallback** (always runs, regardless of `primary_language`): scan for >2
language-specific files in the repo to catch secondary languages and repos with
no root manifest:
- Python → `*.py` count >2 (excluding `.git/`, `node_modules/`, `.venv/`)
- TypeScript/JavaScript → `*.ts`/`*.js` count >2 (excluding `node_modules/`)
- Go → `*.go` count >2

The `>2` threshold deliberately excludes single-file utility scripts — a repo with
one or two `.py` image scripts is not a "Python project," but those imports still
surface in `inferred.py_imports`. Repos with substantial Python (3+ files) get
`python` added to languages.

Runtime versions (in priority order):
- Node: `package.json .engines.node`, then `.nvmrc`, then `.node-version` (strip leading `v`)
- Go: `go.mod go X.Y` line
- Python: `pyproject.toml requires-python`, or Dockerfile `FROM python:X.Y`
- Rust: `Cargo.toml rust-version = "X.Y"` (scanned across all member crates)

### 3. Devcontainer (authoritative when present)
File: `.devcontainer/devcontainer.json` (parsed as JSONC — strips `//` and `/* */` comments)

Extracts:
- `runArgs` → `--cap-add=*` → Docker capabilities (NET_ADMIN, NET_RAW)
- `mounts` → named volumes (both string `source=X,target=Y` and object form)
- `customizations.vscode.extensions` → VS Code extension IDs
- `containerEnv` → env var names
- `postStartCommand` + `postCreateCommand` → init script chain
- `remoteUser` → container username
- `forwardPorts` → inbound ports

Also reads `.vscode/extensions.json` `.recommendations` and merges (deduped).

### 4. Dockerfile (explicit package declarations)
Searches all Dockerfiles recursively (`find . \( -name "Dockerfile" -o -name "Dockerfile.*" \) -not -path "./.git/*"`), including `.devcontainer/Dockerfile`.

Per-Dockerfile Python parsing (join continuation lines first):
- First `FROM` line → `dockerfile_base`
- `apt-get install / apt install / apk add` lines → `system_packages`
- `wget` / `curl -L` lines with release download URLs → `extra_binaries`

### 5. Libraries
- `package.json` → `.dependencies` + `.devDependencies` (cap at 60)
- `requirements.txt` → lines stripped of version specifiers
- `go.mod` → indented `require` lines
- **`Cargo.toml` (all recursively)** → dependency names from `[dependencies]`,
  `[dev-dependencies]`, `[build-dependencies]`, and table form
  `[dependencies.name]` sections. Filters out TOML section keywords
  (`workspace`, `package`, `lib`, `bin`, etc.) to avoid false positives.
  Capped at 80 entries. Rust version (`rust-version = "X.Y"`) extracted here
  and surfaced in `runtime_versions.rust`.

### 6. Ports
- Dockerfile `EXPOSE` directives
- `docker-compose*.yml` port mappings
- `devcontainer.json` `forwardPorts`

### 7. External Services — context-aware, no blocklist
Priority 1 (most authoritative): `init-firewall*.sh` / `firewall*.sh` / `setup-network*.sh`
— Extract quoted domain strings directly; these scripts are ground truth.

Priority 2 (fallback when no firewall script): context-aware scan across all repo files.
Classification is by WHERE the URL appears (file type + code context), not WHAT the domain is.
No blocklist. The only always-skip is localhost/private ranges: `127.*`, `192.168.*`, `10.*`, `0.0.0.0`, `::1`.

**Source code** (`.py`, `.ts`, `.js`, `.go`, `.rs`, `.sh`, `.bash`): only non-comment lines
that contain an HTTP call pattern (`fetch(`, `requests.get(`, `urllib.urlopen(`, `http.Get(`,
`grpc.Dial(`, `curl`, `wget`) → **high confidence**.

**Config/env files** (`.yml`, `.yaml`, `.toml`, `.cfg`, `.ini`, `.conf`, `.env*`, `.json`):
all URLs in these files are runtime configuration → **high confidence**.

**Markdown/docs** (`.md`, `.rst`, `.txt`, `.adoc`):
- Code fences (` ``` ``` `): owner demonstrated a runtime call in docs → **medium confidence**
- Prose lines with service-keyword context (`api`, `service`, `endpoint`, `webhook`, `connect`,
  `host`, `server`, `baseurl`, `origin`, `remote`, `backend`): owner described a runtime dependency → **medium confidence**
- Badge lines (`[![`) are skipped entirely — these are CI/shield widgets, not runtime services

**What IS valid to skip unconditionally:**
- Lock files (`package-lock.json`, `yarn.lock`, `Cargo.lock`, etc.) — install-time noise
- `node_modules/`, `vendor/`, `.venv/` — third-party code, not this repo's deps
- `.svg` files — XML namespace URLs (`w3.org`) in generated SVG
- Localhost/internal IPs — never runtime external services

**README/docs as baseline:** The owner wrote the docs to describe how the project works.
Code fences show actual runtime API calls. Prose keywords identify services the project
connects to. This is valuable signal — it establishes what the owner intends, before
confirming via source code.

### 8. Credentials & Auth
Sources (all combined, deduped by type):
- `.env.example / .env.sample / .env.template` — var names (exclusive routing by suffix/prefix)
- GitHub Actions workflow files — `secrets.<NAME>` references
- Source code — `process.env.NAME` (TS/JS), `os.environ.get('NAME')` (Python), `os.Getenv("NAME")` (Go)

Exclusive routing for all sources — each var goes to exactly one bucket:
1. `_KEY$` or `_SECRET$` → `api_keys`
2. `_TOKEN$` or `_PAT$` → `tokens`
3. Known service prefixes (`DATABASE_URL`, `REDIS_URL`, `SMTP_*`, etc.) → `other`
4. No match → not captured (too generic to classify)

These routing suffixes (`_KEY$`, `_SECRET$`, `_TOKEN$`, `_PAT$`) are industry standard
naming conventions, not a filter list — they're defined by the credential type, not opinions
about specific tools.

**Credential dedup pitfall:** Both the `.env.example` loop AND the workflow secrets loop
must use exclusive `if/elif` routing. If one uses additive independent `if` checks,
a var like `GEMINI_API_KEY` matches both `_KEY$` (api_keys) and `^GEMINI` (other),
appearing in both. Fix applied to both loops.

SSH detection: keyword scan for `ssh / id_rsa / known_hosts / ssh-keygen / ssh-agent / SSH_AUTH_SOCK`
in shell, TS, JS, Python, JSON, YAML files. Excludes `node_modules/`, `vendor/`, `.venv/`, `__pycache__/`
and all lock files — otherwise `package-lock.json` (which contains `git+ssh://` URLs for git-sourced npm
deps) and npm package JSONs trigger false positives on non-SSH repos.

### 9. MCP Servers
- `.mcp.json` / `.claude/mcp.json` / `.claude/settings.json` → `mcpServers` keys
- `package.json` → deps containing `@modelcontextprotocol` or `mcp-server`

### 10. Claude Plugins
- `.claude-plugin/marketplace.json` → `.plugins[].name`
- `SKILL.md` / `PLUGIN.md` file count as indicator

### 11. Environment Variables
Union of:
- `.env.example` and similar var names
- Dockerfile `ENV` directives
- `devcontainer.json` `containerEnv` keys

### 12. Browser / Test Tools
Keyword scan of `package.json / requirements.txt / Pipfile / pyproject.toml / go.mod`:
playwright, puppeteer, selenium, cypress

### 13. Source Code Inference — fully dynamic, no hardcoded lists

Runs always. Critical fallback when no Dockerfile/manifest is present.
Scans: shell scripts (`.sh` + extensionless files with bash shebangs), GitHub
Actions workflow `run:` blocks, and `Makefile`, `makefile`, `GNUmakefile`,
`Taskfile.yml`, `Taskfile.yaml`, `justfile`, `Justfile`.

#### Shell command extraction (no KNOWN_TOOLS list)
Extract the first token after command-position delimiters (`;`, `|`, `&`, `(`, `{`, newline)
in shell/Makefile content. Strip comment lines first.

Filter the extracted token:
- Must be >1 char, no `/`, not start with digit, not all-caps (env var)
- Must not be in `SHELL_BUILTINS` — queried at runtime: `bash -c 'compgen -b; compgen -k'`
- Must not be in `NOISE` — common English words that appear as command tokens but aren't tools

Also detect explicit dependency checks: `command -v X`, `which X`, `type X` patterns.
And shebangs: `#!/usr/bin/env X`.

Result: any binary/tool that the repo actually invokes, regardless of whether it's
in a pre-compiled list.

#### CI/CD workflow action parsing (dynamic, no USES_MAP)
For each `uses: owner/action-name@version` in `.github/workflows/*.yml`:
1. Take the action repo name (second path component, lowercased)
2. Strip standard prefixes: `setup-`, `install-`, `action-`, `run-`
3. Strip standard suffixes: `-action`, `-toolchain`, `-cache`, `-setup`, `-runner`, `-builder`
4. What remains is the tool name — `actions/setup-node` → `node`, `dtolnay/rust-toolchain` → `rust`

This derives the tool dynamically from naming conventions, not a lookup table.
Also extracts commands from `run:` blocks using the same delimiter-pattern approach.

#### Python stdlib — queried from Python, not hardcoded
```python
stdlib_py = frozenset(getattr(sys, 'stdlib_module_names', frozenset()))  # Python 3.10+
if not stdlib_py:
    stdlib_path = sysconfig.get_python_lib(standard_lib=True)
    stdlib_py = frozenset(m.name for m in pkgutil.iter_modules([stdlib_path]))
    stdlib_py = stdlib_py | frozenset(sys.builtin_module_names)
```
`sys.stdlib_module_names` is the authoritative list for the running Python version.
The fallback uses `pkgutil.iter_modules` to enumerate the stdlib path on disk.
Never hardcoded — no maintenance, no gaps.

#### Node.js builtins — queried from Node, not hardcoded
```bash
NODE_BUILTINS_JSON=$(node -e "console.log(JSON.stringify(require('module').builtinModules))" 2>/dev/null || echo "[]")
export AP_NODE_BUILTINS="$NODE_BUILTINS_JSON"
```
Exported immediately after the node call so the INFERRED_SOURCE Python block can read
`os.environ.get('AP_NODE_BUILTINS', '[]')`. If Node is unavailable, falls back to empty
set (no filtering — conservative: better to include a builtin than miss a real dep).

#### Local module filter
Before scanning Python files, collect root-level directory names and `.py` stems:
```python
LOCAL_MODULES = (
    {p.name for p in Path('.').iterdir() if p.is_dir() and not p.name.startswith('.')}
    | {p.stem for p in Path('.').glob('*.py')}
)
```
This prevents `import scripts` (local `scripts/` dir) or `import utils` from appearing
as external packages. Determined by the repo's own structure, not a hardcoded list.

**Dedup logic:**
- `inferred.tools_new` = inferred tools NOT in `system_packages` (net-new gaps)
- `inferred.tools_confirmed` = inferred tools already in `system_packages` (validation)
- Markdown highlights only `tools_new` as actionable items

### 14. System Dependency Resolution — apt-cache + tool-deps.json cache

For each discovered tool (from `inferred.tools` + `inferred.ci_tools`), resolve what
system packages it needs in Layer 1. This is a key function — the analysis directly
informs what goes into the Layer 1 Dockerfile.

**Resolution flow:**
1. Load `tool-deps.json` from the skill directory (alongside `analyze-project.sh`)
2. For each tool not already cached:
   a. Try `apt-cache show <tool>` — if the tool name is itself a Debian package, extract `Depends:` field
   b. If not a direct package, try `dpkg -S */bin/<tool>` to find what package provides the binary
   c. Store result: `{"apt_package": "pkg-name", "apt_depends": ["dep1", ...]}`
   d. If neither resolves → `{"apt_package": null, "apt_depends": []}`
3. Write updated cache back to `tool-deps.json`
4. Surface in `system_deps` field: only tools that resolved to a known package

**tool-deps.json format:**
```json
{
  "jq": {"apt_package": "jq", "apt_depends": ["libjq1", "libonig5"]},
  "gh": {"apt_package": null, "apt_depends": []},
  "myunknowntool": {"apt_package": null, "apt_depends": []}
}
```

`gh` is a good example of a tool that won't resolve via apt (it's installed via a
custom apt source or binary download) — the null result is correct and cached.

**Cache behavior:** Once a tool is in the cache (even as null), it won't be re-queried.
The cache grows as new tools are discovered. Results in `system_deps` are written to
`analysis.json` and shown in the Markdown report.

### 15. Firewall Flag
Set `firewall_required: true` if:
- Any `init-firewall*` / `firewall*.sh` script found in repo
- `devcontainer.json` `runArgs` includes `NET_ADMIN` or `NET_RAW`

### 16. Suggested Stack
- `base_image`: layer1 variant tag — `playwright_with_chromium` if browser tools detected, else `latest`
- `dockerfile_from`: ideal `FROM` for a dedicated Dockerfile — derived from existing `dockerfile_base`
  if present, otherwise inferred from language + `runtime_versions`:
  `rust:1.88`, `golang:1.21`, `python:3.12`, `node:lts`
- `ai_install`: always `claude` (default; could be parameterized)
- `plugin_layer`: empty — resolved at build-workspace runtime by querying GHCR
- `dockerfile_from` fallback: `node:lts`, `python:3`, `golang:latest`, `rust:latest` — never `python:latest`
  (`python:latest` is an anti-pattern; `python:3` pins to the Python 3 branch at minimum)

---

## JSON Schema (current)

```json
{
  "repo":             "owner/repo",
  "project":          "repo",
  "analyzed_at":      "YYYY-MM-DD",
  "purpose":          "...",
  "primary_language": "Rust",
  "languages":        ["rust", "shell"],
  "runtime_extras":   [],
  "runtime_versions": {"rust": "1.88"},
  "dockerfile_base":  "",
  "system_packages":  [],
  "extra_binaries":   [],
  "libraries": {
    "node":   [],
    "python": [],
    "go":     [],
    "rust":   ["axum", "tokio", "serde"]
  },
  "ports": {
    "inbound": []
  },
  "external_services": {
    "domains": ["api.example.com"],
    "source":  "source_scan"
  },
  "env_vars": [],
  "browser_tools": [],
  "github_api_usage": false,
  "firewall_required": false,
  "container": {
    "capabilities": [],
    "volumes": [],
    "env": {},
    "remote_user": "",
    "post_start": "",
    "post_create": "",
    "extensions": []
  },
  "credentials_required": {
    "api_keys": [],
    "tokens":   ["GITHUB_TOKEN"],
    "ssh":      false,
    "other":    []
  },
  "mcp_servers":    [],
  "claude_plugins": [],
  "inferred": {
    "tools":           ["buf", "cargo", "curl", "docker", "gh"],
    "tools_new":       ["buf", "cargo", "curl", "docker", "gh"],
    "tools_confirmed": [],
    "py_imports":      [],
    "ts_imports":      [],
    "ci_tools":        ["rust", "node"]
  },
  "system_deps": {
    "curl": {"apt_package": "curl", "apt_depends": ["libcurl4", "libssl3"]},
    "jq":   {"apt_package": "jq",   "apt_depends": ["libjq1", "libonig5"]}
  },
  "suggested": {
    "base_image":      "latest",
    "dockerfile_from": "rust:1.88",
    "ai_install":      "claude",
    "plugin_layer":    ""
  }
}
```

---

## Known Gaps & Planned Improvements

### Gap 1: npm global installs from Dockerfile
`RUN npm install -g @anthropic-ai/claude-code` installs a global binary, not
a library. These should surface in `extra_binaries` or a new `global_npm` field,
not be lost. Current regex looks only for `releases/download/` patterns.

**Fix:** Add npm global install detection in Python Dockerfile parser:
`re.findall(r'npm install -g ([\S]+)', line)`

### Gap 2: Credential bind-mount files as auth signals
The Layer 4 repo mounts `/run/credentials/gh_pat` and `/run/credentials/gh_claude_ed25519`.
These appear in `container.volumes` but are not cross-referenced into
`credentials_required`. A consumer has to know to look there.

**Fix:** Post-process volumes — any bind mount with `/run/credentials/` in the
target path should be extracted as an auth signal and surfaced in credentials.

### Gap 3: init-script chain parsing
`postStartCommand` can be a chain like:
`sudo /usr/local/bin/init-firewall.sh && /workspace/.devcontainer/scripts/init-ssh.sh && ...`

Each init script may add more dependencies (SSH keys, GH tokens, project repos).
Currently captured as a raw string; could be parsed to enumerate each script and
what it sets up.

**Fix:** Split `&&` chain → per-script list. Then scan each script for what it
installs/configures and add those signals to the appropriate categories.

### Gap 4: npm/pip/go installs inside Dockerfile RUN blocks
`RUN npm install`, `RUN pip install X`, `RUN go install X` inside a Dockerfile
RUN block beyond the standard package manager call. These add runtime dependencies
but are currently missed unless they appear in `package.json` or `requirements.txt`.

**Fix:** In Python Dockerfile parser, also extract:
- `npm install -g <pkg>` / `npm ci` (look for package.json alongside)
- `pip install <pkg>` one-liners
- `go install <pkg>@<version>`

### Gap 5: TS/JS import dedup vs package.json
`inferred.ts_imports` will list packages like `@anthropic-ai/sdk` that are
already in `libraries.node`. Same dedup logic as tools vs system_packages
should apply here.

**Fix:** After building `data`, compute:
`inferred['ts_imports_new'] = sorted(set(ts_imports) - set(node_libs))`

---

## Integration with build-workspace

When `analyze-project` feeds `build-workspace`, the consumer mapping is:

| analysis.json field | build-workspace layer | Usage |
|---|---|---|
| `suggested.base_image` | Layer 1 | Pre-select base image variant |
| `suggested.dockerfile_from` | Layer 1 | Suggested FROM for custom Dockerfile |
| `suggested.ai_install` | Layer 2 | Pre-select claude vs gemini |
| `suggested.plugin_layer` | Layer 3 | Pre-select plugin layer (if known) |
| `system_packages` + `inferred.tools_new` | Layer 1 Dockerfile | apt-get packages to add |
| `system_deps` | Layer 1 Dockerfile | Resolved apt packages for inferred tools |
| `external_services.domains` | Layer 1 init-firewall.sh | Allowlist domains |
| `container.capabilities` | Layer 4 devcontainer.json `runArgs` | `--cap-add` flags |
| `container.volumes` | Layer 4 devcontainer.json `mounts` | Named volumes + credential mounts |
| `container.env` | Layer 4 devcontainer.json `containerEnv` | Env var passthroughs |
| `container.post_start` | Layer 4 devcontainer.json | `postStartCommand` |
| `container.extensions` | Layer 4 devcontainer.json | VS Code extensions |
| `credentials_required` | Layer 4 init scripts | Determine which init-*.sh are needed |
| `mcp_servers` | Layer 4 `.mcp.json` | MCP server config |
| `firewall_required` | Layer 4 devcontainer.json | Include `--cap-add NET_ADMIN/NET_RAW` |
| `ports.inbound` | Layer 4 devcontainer.json `forwardPorts` | Port forwarding |
| `libraries.rust` | Layer 1 Dockerfile (rustup/cargo) | Rust crate deps for build cache |
| `inferred.ci_tools` | Layer 1 Dockerfile | Additional tools revealed by CI config |

---

## Testing Strategy

Test against repos representing diverse profiles:

| Repo | Profile | Tests |
|---|---|---|
| `anthropics/claude-code` | Node/bun, Dockerfile, firewall, plugins | System pkgs, domains, caps, plugins |
| `sun2admin/build-containers-with-claude` | Shell-only, no Dockerfile, credential mounts | Inference, SSH, volumes |
| `sun2admin/builder-project` | Multi-layer, mixed shell+YAML | Cross-file inference |
| `anthropics/connect-rust` | Rust, Cargo workspace, Taskfile, no Dockerfile | Rust libs, CI tools, suggested FROM |
| `santifer/career-ops` | Node, Playwright, .env.example, data-file URLs | HTML purpose, cred dedup, nvmrc |
| `danielrosehill/claude-code-projects-index` | Astro static site, package-lock.json noise | node_modules exclusion, lock file exclusion |
| `anthropics/claude-code-security-review` | GitHub Action, Python+bun, no root manifests | TS stdlib filter, language file-scan fallback |
| `peterkrueck/claude-code-development-kit` | Shell+Python utilities, no manifests | Unconditional language file-scan |
| `hesreallyhim/awesome-claude-code` | Python automation, awesome list README | Blockquote skip, README short-snippet fallback, local module filter |

For each test: verify JSON parses cleanly, all known facts appear in the right
field, no false positives from comment/prose scanning.

---

## Implementation Notes

### Temp clone lifecycle
`TEMP_DIR=$(mktemp -d "/tmp/analyze-${REPO_NAME}-XXXXX")`
`trap cleanup EXIT` — guaranteed cleanup even on error exit.
Caller never sees the clone path; stdout gets only `analysis.json` path.

### No interactive input
Skill takes `owner/repo` as `$1` or prompts once via `read_input`. Designed to
be called non-interactively from `build-workspace`.

### lib.sh dependency
Sources `../build-workspace/lib.sh` for `read_input`, color vars (`$BLUE`, `$GREEN`,
`$RED`, `$NC`). All display output goes to `>&2` so stdout carries only the
JSON file path for capture: `result=$(bash analyze-project.sh repo 2>/dev/tty)`.

### Builds registry
Results saved to `builds/<owner>/<repo>/analysis.json` inside the builder-project repo,
mirroring the GitHub `owner/repo` hierarchy. This organizes builds by user/org at the
top level — `builds/anthropics/`, `builds/sun2admin/`, etc.

**Two-level navigation for build-workspace:**
When a user asks to load or resume an existing analysis, the flow is:
1. List unique owners: `ls builds/` → show as menu
2. User picks an owner → list that owner's repos: `ls builds/<owner>/`
3. User picks a repo → load `builds/<owner>/<repo>/analysis.json`

This replaces the previous flat list of all repo names, which becomes hard to
read when multiple owners have repos with similar names.

Results are version-controlled and can be compared across runs.
The `builds/` dir is gitignored for generated artifacts but `analysis.json` and
`analysis.md` are committed intentionally.

### Cargo.toml workspace pattern
Rust projects often have a root workspace `Cargo.toml` plus per-crate `Cargo.toml`
files in subdirectories. Always use `Path('.').rglob('Cargo.toml')` to scan all of
them. The `TOML_SECTIONS` set filters keyword section names that look like
dependency names in naive regex (`workspace`, `package`, `lib`, etc.). TOML_SECTIONS
is a legitimate hardcoded set — it's defined by Cargo's fixed schema, not opinions.

### tool-deps.json
Stored at `.claude/skills/analyze-project/tool-deps.json` alongside the skill.
Initial state: `{}`. Grows over time as new tools are discovered across analyzed repos.
Committed to version control so it persists across sessions and containers.
The file is written only when new tools are encountered (cache_updated flag).
