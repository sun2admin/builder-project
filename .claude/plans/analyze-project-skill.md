# analyze-project Skill Plan

**Skill path:** `.claude/skills/analyze-project/analyze-project.sh`
**Output path:** `builds/<project>/analysis.json` + `builds/<project>/analysis.md`
**Status:** Active development — core working, iterating on coverage

---

## Purpose

Scan any GitHub repo and produce a complete dependency + configuration map
needed to stand up that project inside our 4-layer container stack. The output
feeds directly into `build-workspace` as structured inputs for each layer skill,
and is also human-readable for review.

---

## Architecture Principles

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

### pipefail + grep exit-1 trap
`set -euo pipefail` makes any failing command in a pipeline abort the script.
`grep` exits 1 when no matches found — even on a clean run. Fix: wrap grep
inside `{ grep ... || true; }` in any pipeline that feeds into Python JSON
serialization. Without this, Python prints valid JSON, then `|| echo "[]"` 
appends another `[]`, producing `[]\n[]` which fails `json.loads()`.

### Python for structured file parsing; bash for orchestration
- Bash: clone, file discovery, loop iteration, env var setup
- Python: JSON generation, JSONC parsing, Dockerfile parsing, regex extraction
- Never mix: bash `echo "$VAR" | python3` is fine; generating JSON in bash
  with string concatenation is not.

### Continuation-line Dockerfile parsing
`grep` sees only the first line of a multi-line `RUN` command. The package
list is on backslash-continuation lines. Always use Python to join `\`-continued
lines before extracting packages, base images, or binary downloads.

### find patterns: always exclude .git
Use `-not -path "./.git/*"` in all `find` calls. `grep -v ".git"` is
insufficient when paths contain `.git` as a directory component.

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
| Purpose | README.md first paragraph | Strip badges, HTML, headings; take first real paragraph ≥30 chars |
| Purpose fallback | `gh api repos/<owner>/<repo>` `.description` | Used when README has no parseable text |
| Primary language | GitHub API `.language` | Authoritative; language files are unreliable |

### 2. Languages & Runtimes
Detected by file presence at repo root:
- `package.json` → node
- `requirements.txt / setup.py / Pipfile / pyproject.toml` → python
- `Gemfile` → ruby, `go.mod` → go, `Cargo.toml` → rust, `pom.xml / build.gradle` → java
- `*.sh` files → shell

Runtime extras (supplement, not replace):
- `bun.lockb / bun.lock` or `#!/usr/bin/env bun` shebang → bun
- `deno.json / deno.lock` → deno
- `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn

Runtime versions: `package.json .engines.node`, `go.mod go X.Y` line,
`Cargo.toml rust-version = "X.Y"` (scanned across all member crates)

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

### 7. External Services (firewall domains)
Priority 1 (most authoritative): `init-firewall*.sh` / `firewall*.sh` / `setup-network*.sh`
— Extract quoted domain strings: `grep -oP '"[a-z0-9][a-z0-9.-]+\.[a-z]{2,}"'`

Priority 2 (fallback when no firewall script): URL pattern scan across
`*.ts *.js *.py *.go *.rs *.sh *.json *.yml *.yaml` (excluding `gen/`, `generated/` dirs and `.svg` files).
Domain blocklist removes known noise: `example.com`, `localhost`, `w3.org`,
`schema.org`, `iana.org`, `rfc-editor.org`, `acme.com`, `shields.io`,
`travis-ci.*`, `codecov.io`, `badge.*`.

**URL noise sources discovered in testing:**
- `w3.org` from SVG XML namespace declarations in generated SVG files
- `acme.com` from generated Go ACME client code comments
- Fix: exclude `gen/` and `generated/` directories, skip `.svg` files

### 8. Credentials & Auth
Sources (all combined, deduped by type):
- `.env.example / .env.sample / .env.template` — var names matching `_KEY$`, `_TOKEN$`, `_PAT$`
- GitHub Actions workflow files — `secrets.<NAME>` references (exclusive routing: `_KEY$` → api_keys, `_TOKEN$|GITHUB_TOKEN` → tokens, else → other)
- Source code — `process.env.NAME` (TS/JS), `os.environ.get('NAME')` (Python), `os.Getenv("NAME")` (Go)

**Credential dedup pitfall:** The workflow secrets loop must use exclusive
`if/elif/else` routing — not additive conditionals — or the same secret appears
in multiple categories (e.g., `CARGO_REGISTRY_TOKEN` in both tokens and other).

SSH detection: keyword scan for `ssh / id_rsa / known_hosts / ssh-keygen / ssh-agent / SSH_AUTH_SOCK`
in shell, TS, JS, Python, YAML files.

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

### 13. Source Code Inference
Runs always. Critical fallback when no Dockerfile/manifest is present.
Scans: shell scripts (`.sh` + extensionless files with bash shebangs), GitHub
Actions workflow `run:` blocks, and `Makefile`, `makefile`, `GNUmakefile`,
`Taskfile.yml`, `Taskfile.yaml`, `justfile`, `Justfile`.

**Note:** Both `Taskfile.yml` and `Taskfile.yaml` must be checked — different
projects use different extensions.

For each file, tests presence of ~80 known installable binaries via
`re.search(r'\b<tool>\b', content)`. KNOWN_TOOLS includes language-specific
tools (`rustup`, `cargo`, `buf`, `protoc`, `grpc`, `task`, `valkey`) as well
as common dev tooling.

Also scans:
- Python files for non-stdlib `import` statements → `inferred.py_imports`
- TS/JS files (excluding `node_modules/`) for named module imports → `inferred.ts_imports`

**GitHub Actions `uses:` step detection:**
Maps known CI action prefixes to the tool they install. Added to
`inferred.ci_tools` (separate from `tools` to preserve provenance):
```
dtolnay/rust-toolchain → rust
actions-rs/toolchain   → rust
arduino/setup-protoc   → protoc
bufbuild/buf-setup-action → buf
actions/setup-node     → node
actions/setup-python   → python3
actions/setup-go       → go
actions/setup-java     → java
ruby/setup-ruby        → ruby
Swatinem/rust-cache    → rust
PyO3/maturin-action    → rust
```

**Dedup logic:**
- `inferred.tools_new` = inferred tools NOT in `system_packages` (net-new gaps)
- `inferred.tools_confirmed` = inferred tools already in `system_packages` (validation)
- Markdown highlights only `tools_new` as actionable items

### 14. Firewall Flag
Set `firewall_required: true` if:
- Any `init-firewall*` / `firewall*.sh` script found in repo
- `devcontainer.json` `runArgs` includes `NET_ADMIN` or `NET_RAW`

### 15. Suggested Stack
- `base_image`: layer1 variant tag — `playwright_with_chromium` if browser tools detected, else `latest`
- `dockerfile_from`: ideal `FROM` for a dedicated Dockerfile — derived from existing `dockerfile_base`
  if present, otherwise inferred from language + `runtime_versions`:
  `rust:1.88`, `golang:1.21`, `python:3.12`, `node:lts`
- `ai_install`: always `claude` (default; could be parameterized)
- `plugin_layer`: empty — resolved at build-workspace runtime by querying GHCR

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
    "rust":   ["axum", "tokio", "serde", ...]
  },
  "ports": {
    "inbound": []
  },
  "external_services": {
    "domains": ["demo.connectrpc.com", "github.com"],
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
    "tokens":   ["CARGO_REGISTRY_TOKEN", "GITHUB_TOKEN"],
    "ssh":      false,
    "other":    []
  },
  "mcp_servers":    [],
  "claude_plugins": [],
  "inferred": {
    "tools":           ["buf", "cargo", "curl", "docker", "gh", ...],
    "tools_new":       ["buf", "cargo", "curl", "docker", "gh", ...],
    "tools_confirmed": [],
    "py_imports":      [],
    "ts_imports":      [],
    "ci_tools":        ["rust", "protoc", "buf"]
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

### Gap 5: Inferred tool list noise from comments/prose
Some tools in `KNOWN_TOOLS` appear in comments or README text, not actual
invocations — e.g., a repo that mentions `gradle` in a comparison table.
Current implementation does `re.search(r'\bgradle\b', content)` which matches
anywhere including prose.

**Fix:** For shell scripts, restrict search to lines that are NOT comments
(strip `#`-prefixed lines before scanning). For prose files like README.md,
exclude from tool scanning entirely.

### Gap 6: No Dockerfile + no shell scripts (pure Python repos)
Pure Python repo with only `.py` files and `requirements.txt`. Currently
`system_packages` will be empty and `inferred.tools` will also be empty.
The `py_imports` will be populated.

**Fix:** For Python projects without a Dockerfile, add a mapping from common
third-party imports to their system prerequisites — e.g., `cv2` → `libopencv`,
`psycopg2` → `libpq-dev`, `Pillow` → `libjpeg-dev`. Small curated lookup table.

### Gap 7: TS/JS import dedup vs package.json
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
| A pure Python repo | No Dockerfile, no shell scripts | py_imports, no Dockerfile fallback |
| A Go service with docker-compose | Go, ports, DB clients | ports, go libs, DB detection |
| A frontend React app | TS, npm, no container | TS inference, node libs |

For each test: verify JSON parses cleanly, all known facts appear in the right
field, no false positives from comment/prose scanning.

---

## Implementation Notes

### Temp clone lifecycle
`TEMP_DIR=$(mktemp -d "/tmp/analyze-${PROJECT}-XXXXX")`
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
Results saved to `builds/<project>/analysis.json` inside the builder-project repo.
This means analysis results are version-controlled and can be compared across runs.
The `builds/` dir is gitignored for generated artifacts but `analysis.json` and
`analysis.md` are committed intentionally.

### Cargo.toml workspace pattern
Rust projects often have a root workspace `Cargo.toml` plus per-crate `Cargo.toml`
files in subdirectories. Always use `Path('.').rglob('Cargo.toml')` to scan all of
them. The `TOML_SECTIONS` set filters keyword section names that look like
dependency names in naive regex (`workspace`, `package`, `lib`, etc.).
