---
name: analyze-project
description: Scan a GitHub project repo for all dependencies needed to build a container stack. Use this skill when the user wants to analyze a project's dependencies, detect system packages/libraries/ports/env vars, or prepare inputs for an auto build. Invoke for any request involving scanning a repo, detecting dependencies, or running analyze-project.
---

# /analyze-project

Clones a GitHub repo fresh and scans it for all dependencies needed to configure a container stack. Saves findings to `builds/<project>/analysis.json` and `builds/<project>/analysis.md`.

## Usage

```
/analyze-project [owner/repo]
```

Prompts for repo if not provided.

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

- `builds/<project>/analysis.json` — machine-readable, consumed by build-workspace for auto builds
- `builds/<project>/analysis.md` — human-readable summary displayed to user
- **stdout**: path to analysis.json (for skill-to-skill consumption)

## Suggested Stack Logic

- `base_image`: `playwright_with_chromium` if browser tools detected, else `latest`
- `ai_install`: `claude` (default)
- `plugin_layer`: empty — build-workspace queries GitHub dynamically at build time

## Integration with build-workspace

When `build-workspace` runs in auto mode, it reads `suggested` from `analysis.json`:

```bash
BASE_IMAGE=$(jq -r '.suggested.base_image' builds/<project>/analysis.json)
AI_INSTALL=$(jq -r '.suggested.ai_install' builds/<project>/analysis.json)
```

The full findings (languages, ports, packages) are preserved in `analysis.json` for future reference and can inform dedicated layer creation.
