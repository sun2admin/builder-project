---
name: analyze-repo
description: Scan a GitHub project repo for all dependencies needed to build a container stack. Use this skill when the user wants to analyze a project's dependencies, detect system packages/libraries/ports/env vars, or prepare inputs for an auto build. Invoke for any request involving scanning a repo, detecting dependencies, or running analyze-repo.
---

# /analyze-repo

Clones a GitHub repo fresh and scans it for all dependencies needed to configure a container stack. Saves findings to `analyzed_repos/<owner>/<repo>/analysis.json` and `analyzed_repos/<owner>/<repo>/analysis.md`.

## Reference Docs — Read Before Modifying

| File | When to load |
|---|---|
| [`DETECTION_PRINCIPLES.md`](./DETECTION_PRINCIPLES.md) | Editing detection logic (regex, parsers, filters, bash/Python idioms) |
| [`DATA_SCHEMA.md`](./DATA_SCHEMA.md) | Editing output JSON shape, builds dir layout, tool-deps.json, consumer contract |
| [`TESTING.md`](./TESTING.md) | Validating gap fixes, adding test repos, regression checking |

Core detection rule: derive from the artifact, never compare against an
opinion list. No `KNOWN_TOOLS`/`STDLIB_*`/`COMMON_DOMAINS` arrays. Use
runtime queries (`apt-cache`, `sys.stdlib_module_names`,
`node -e builtinModules`) or cached lookups (`tool-deps.json`). Cover tool
families, not single members (npm+yarn+pnpm+bun, pip+pipx, etc.).

## Usage

```
/analyze-repo [-q|--quiet] [-v|--verbose] [owner/repo]
```

Prompts for repo if not provided.

**Output channels:**
- **stdout** — JSON file path (single line, always)
- **stderr** — progress traces; full markdown report when emit enabled

**Markdown emit decision (auto-detect with override):**
- `-q` / `--quiet` → suppress markdown
- `-v` / `--verbose` → emit markdown regardless of TTY
- Default: emit when stdout is a terminal; suppress when piped/captured

**Why:** when invoked by `build-workflow` (or any wrapper), markdown noise
floods the wrapper's terminal. Default TTY-aware behavior keeps wrapper
output clean while preserving direct-user UX.

**Files saved regardless of emit:**
- `analyzed_repos/<owner>/<repo>/analysis.json`
- `analyzed_repos/<owner>/<repo>/analysis.md`

## What It Detects

| Category | Sources Scanned |
|---|---|
| Languages | package.json, requirements.txt, Pipfile, pyproject.toml, setup.py, Gemfile, go.mod, Cargo.toml, pom.xml, build.gradle, composer.json |
| System packages | Dockerfile RUN apt-get/apt/apk install lines, devcontainer.json features |
| Libraries | package.json dependencies+devDependencies, requirements.txt, go.mod require blocks, Pipfile packages |
| Ports | Dockerfile EXPOSE, docker-compose.yml ports section, common source patterns |
| Env vars | .env.example/.env.sample/.env.template, Dockerfile ENV, docker-compose.yml environment |
| Browser tools | playwright, puppeteer, selenium, cypress (drives base image suggestion) |
| GitHub API | @octokit, PyGithub, go-github, Octokit references |

## Output

- `analyzed_repos/<owner>/<repo>/analysis.json` — machine-readable, consumed by `/build-stack` skill + tool
- `analyzed_repos/<owner>/<repo>/analysis.md` — human-readable summary displayed to user
- **stdout**: path to analysis.json (for skill-to-skill consumption)

## Suggested Stack Logic

- `base_image`: `playwright_with_chromium` if browser tools detected, else `latest`
- `ai_install`: `claude` (default)
- `plugin_layer`: empty — build-workspace queries GitHub dynamically at build time

## Integration with build-stack

The `/build-stack` skill invokes `/analyze-repo` once per referenced repo (project repo + each plugin repo). The tool's compose pipeline then reads pre-existing `analyzed_repos/<owner>/<repo>/analysis.json` files and aggregates them into a single build composition. The skill never re-runs analyze inside the tool — it only reads from cache.

```bash
BASE_IMAGE=$(jq -r '.suggested.base_image' analyzed_repos/<owner>/<repo>/analysis.json)
AI_INSTALL=$(jq -r '.suggested.ai_install' analyzed_repos/<owner>/<repo>/analysis.json)
```

The full findings (languages, ports, packages) are preserved in `analysis.json` for future reference and can inform dedicated layer creation.
