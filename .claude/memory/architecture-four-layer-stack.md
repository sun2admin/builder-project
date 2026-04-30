---
name: Four-Layer Container Architecture
description: Complete stack from base system packages to devcontainer; how each layer builds on the previous; builder-project as control plane
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## The Four-Layer Architecture (Bottom to Top)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 4: Devcontainer Repos                             │
│ (e.g. build-containers-with-claude)                     │
│ devcontainer.json + init scripts + load-projects.sh     │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Plugin Containers                              │
│ (8 standalone repos: claude-plugins-*, claude-anthropic-*) │
│ Contains: pre-baked plugins via CLAUDE_CODE_PLUGIN_*    │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: layer2-ai-install                              │
│ (:claude and :gemini variants)                          │
│ Installs: Claude Code/Gemini CLI, user setup            │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 1: layer1-ai-depends                              │
│ Tag variants: :light, :latest, :playwright_with_*       │
│ Contains: system packages (Node, Python, git, etc.)     │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1: layer1-ai-depends

**Repo**: `sun2admin/layer1-ai-depends`
**Image**: `ghcr.io/sun2admin/layer1-ai-depends`
**Source in builder-project**: `layer1-ai-depends/`

**Tag Variants**:
- `:light` — Anthropic-recommended minimal packages only
- `:latest` — full extras (Python, dev tools, graphics libs, Jupyter, weasyprint, pandas, numpy)
- `:playwright_with_chromium` — :latest + Chromium pre-baked
- `:playwright_with_firefox` — :latest + Firefox pre-baked
- `:playwright_with_safari` — :latest + WebKit (Safari) pre-baked
- `:playwright_with_all` — ❌ exceeds GitHub Actions runner time limit, do not attempt rebuild

**Dockerfile Structure**:
- `FROM node:22-slim` base
- `playwright-builder` multi-stage: conditionally installs browsers
- `INCLUDE_EXTRAS` ARG: adds Python, dev tools, graphics libs
- `INCLUDE_PLAYWRIGHT` ARG: copies playwright cache into final image

**CI/CD**: GitHub Actions matrix build in standalone repo's `build-and-push.yml`. Triggered by push when `Dockerfile` or `init-firewall.sh` changes.

---

## Layer 2: layer2-ai-install

**Repo**: `sun2admin/layer2-ai-install`
**Image**: `ghcr.io/sun2admin/layer2-ai-install`
**Source in builder-project**: `layer2-ai-install/`
**Base**: `ghcr.io/sun2admin/layer1-ai-depends:latest`

**Tag Variants**:
- `:claude` — Claude Code CLI + `claude` user
- `:gemini` — Gemini CLI + `gemini` user

**How it works**:
- Single Dockerfile with conditional ARG logic (AI_TYPE, AI_PACKAGE, USERNAME)
- All setup baked into image at build time (no features needed)
- GitHub Actions matrix builds both variants in parallel

---

## Layer 3: Plugin Containers

**8 standalone repos** (currently edited directly; consolidation into builder-project planned):
- `claude-anthropic-base-plugins-container` (10 base plugins)
- `claude-anthropic-coding-plugins-container` (10 base + 22 coding)
- `claude-anthropic-ext-plugins-container` (10 base + 15 external)
- `claude-anthropic-all-plugins-container` (10 base + 22 coding + 15 external = 47 total)
- `claude-plugins-a7f3d2e8` (18 plugins — builder-project variant)
- `claude-plugins-3f889e47` (base + document-skills, 11 plugins)
- `claude-plugins-34e199d2` (base + document-skills + 15 external, 26 plugins)
- `claude-plugins-54ca621f` (base + external subset)

**All built on**: `ghcr.io/sun2admin/layer2-ai-install:claude`

**How Plugins Are Baked**:
- `claude plugin marketplace add` then `claude plugin install` at Docker build time
- `CLAUDE_CODE_PLUGIN_CACHE_DIR` + `CLAUDE_CODE_PLUGIN_SEED_DIR` env vars
- Cached at `/opt/claude-custom-plugins`

**Marketplace Sources**:
- `anthropics/claude-plugins-official` — base, coding, and external_plugins/
- `anthropics/skills` — only `document-skills` available in anthropic-agent-skills namespace

---

## Layer 4: Devcontainer Repos

**Purpose**: Sets up the container environment, runs init scripts, loads AI project repos.
**Source in builder-project**: `layer4-devcontainer/` (reference template)
**Example standalone repo**: `sun2admin/build-containers-with-claude`

Devcontainer repos contain: devcontainer.json, init scripts, `load-projects.sh`.
They reference a Layer 3 plugin image and load project repos (like `builder-project`) at startup.

---

## Project Repos (separate concept, not part of the stack)

AI/Claude project files only (CLAUDE.md, .claude/, memory, .mcp.json). Not part of the container architecture. Loaded by `load-projects.sh` at container start.

- `builder-project` is the reference example

---

## Dependency Flow

When layer1-ai-depends is updated:
1. Claude pushes changes from `layer1-ai-depends/` to `sun2admin/layer1-ai-depends`
2. Standalone repo CI/CD builds new `layer1-ai-depends` images
3. `layer2-ai-install` rebuilt (FROM layer1-ai-depends:latest)
4. All 8 plugin repos rebuilt (FROM layer2-ai-install:claude)
5. Layer 4 devcontainer repos pick up new stack on next devcontainer rebuild

---

## Current Status (2026-04-30)

✅ **Layer 1**: layer1-ai-depends — 5/6 variants published (:playwright_with_all excluded)
✅ **Layer 2**: layer2-ai-install — :claude and :gemini published
✅ **Layer 3**: All 8 plugin repos building successfully on layer2-ai-install:claude
✅ **Layer 4**: build-containers-with-claude loads builder-project as live project
