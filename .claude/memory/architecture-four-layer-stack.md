---
name: Four-Layer Container Architecture
description: Complete stack from base system packages to project repos; how each layer builds on the previous
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## The Four-Layer Architecture (Bottom to Top)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 4: Project Repos │
│ (.devcontainer/devcontainer.json references plugins) │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: AI-Plugins Container │
│ (e.g., claude-plugins-a7f3d2e8, claude-plugins-coding) │
│ Contains: pre-baked plugins via CLAUDE_CODE_PLUGIN_* │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: AI-Install Container (layer2-ai-install) │
│ (:claude and :gemini variants) │
│ Installs: Claude Code/Gemini CLI, user setup, init │
└─────────────────────────────────────────────────────────┘
 ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 1: layer1-ai-depends (Base Image) │
│ Tag Variants: :light, :latest, :playwright_with_* │
│ Contains: system packages (Node, Python, git, etc.) │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1: layer1-ai-depends

**Purpose**: Minimal base with system packages, no AI tools or user config.

**Source**: Subdirectory within `sun2admin/builder-project` (single repo for all layers)

**Tag Variants**:
- `:light` — Anthropic-recommended minimal packages only
- `:latest` — full extras (Python, dev tools, graphics libs, Jupyter, weasyprint, pandas, numpy)
- `:playwright_with_chromium` — :latest + Chromium pre-baked
- `:playwright_with_firefox` — :latest + Firefox pre-baked
- `:playwright_with_safari` — :latest + WebKit (Safari) pre-baked
- `:playwright_with_all` — :latest + all three browsers pre-baked

**Dockerfile Structure**:
- FROM node:20-slim
- Layer 1 RUN: Always install :light packages (Anthropic minimal)
- Layer 2 RUN: Conditionally install extras if INCLUDE_EXTRAS=true
- playwright-builder stage: Conditionally install Playwright browsers based on BROWSERS ARG
- final stage: Conditionally copy Playwright cache if INCLUDE_PLAYWRIGHT=true

**Build Args**:
- `INCLUDE_EXTRAS=true|false` (for :latest vs :light)
- `INCLUDE_PLAYWRIGHT=true|false` (for playwright_with_* variants)
- `BROWSERS=chromium|firefox|webkit|...` (space-separated list, empty for :light)

**CI/CD**: GitHub Actions matrix build in `.github/workflows/build-and-push.yml` builds all 6 variants in parallel.

---

## Layer 2: AI-Install Layer (layer2-ai-install)

**Purpose**: Installs AI tool (Claude Code or Gemini CLI) and creates corresponding user with environment setup.

**Source**: Subdirectory within `sun2admin/builder-project` (single repo for all layers)

**Tag Variants**:
- `:claude` — Claude Code CLI + `claude` user
- `:gemini` — Gemini CLI + `gemini` user

**How it works**:
- Single Dockerfile with conditional ARG logic (AI_TYPE, AI_PACKAGE, USERNAME)
- Builds from `layer1-ai-depends:latest`
- All setup baked into image at build time (no features needed)
- GitHub Actions matrix builds both variants in parallel
- Status: ✅ Published and working


---

## Layer 3: AI-Plugins Container

**Purpose**: Pre-bakes Claude Code plugins for efficiency; no manual plugin discovery/download at runtime.

**8 Official Containers**:
- `claude-anthropic-base-plugins-container` (10 base plugins for any project)
- `claude-anthropic-coding-plugins-container` (10 base + 22 coding plugins)
- `claude-anthropic-ext-plugins-container` (10 base + 15 external plugins)
- `claude-anthropic-all-plugins-container` (10 base + 22 coding + 15 external = 47 total)
- `claude-plugins-a7f3d2e8` (build-with-claude variant, 18 plugins for repo creation)
- `claude-plugins-3f889e47` (base + document-skills, 11 plugins)
- `claude-plugins-34e199d2` (base + document-skills + 15 external, 26 plugins)
- `claude-plugins-54ca621f` (base + external subset)

**Tag Variants** (per plugin layer):
- `:latest` — built on layer2-ai-install:claude (which uses layer1-ai-depends:latest)

**How Plugins Are Baked**:
- Dockerfile runs `claude plugin marketplace add` then `claude plugin install` at build time
- Sets `CLAUDE_CODE_PLUGIN_CACHE_DIR` and `CLAUDE_CODE_PLUGIN_SEED_DIR` env vars
- Plugins are cached in the image at `/opt/claude-custom-plugins`
- Claude Code uses plugin cache at startup (no download/auth needed at runtime)

**Marketplace Sources** (validated):
- `anthropics/claude-plugins-official` — base + coding plugins + external_plugins/ directory
- `anthropics/skills` — only `document-skills` available in anthropic-agent-skills namespace

---

## Layer 4: Project Repos

**Purpose**: Actual work happens here; references a plugins layer image.

**Example**: `/workspace/.devcontainer/devcontainer.json`
```json
{
 "image": "ghcr.io/sun2admin/claude-plugins-a7f3d2e8:latest"
}
```

**Key Points**:
- Project repos reference Layer 3 (plugins) image directly
- Image includes all setup from Layers 1, 2, and 3 (no features needed)
- Changes to Layer 1 (layer1-ai-depends) cascade through Layers 2 and 3 via Dockerfile FROM statements
- Project repos do NOT need updates when layer1-ai-depends changes (rebuild plugins layer and it automatically uses new base)

---

## Dependency Flow

When layer1-ai-depends is updated:
1. layer1-ai-depends CI/CD: Builds 6 tag variants automatically
2. layer2-ai-install Dockerfile: `FROM ghcr.io/sun2admin/layer1-ai-depends:latest` → Rebuild to inherit new base
3. Plugin container Dockerfiles: `FROM ghcr.io/sun2admin/layer2-ai-install:claude` → Rebuild to inherit new base
4. Project repos: On next devcontainer rebuild, automatically use new stack

**No project repo code changes needed** — rebuild flows automatically through dependency chain:
- Update Layer 1 → rebuild Layer 2 → rebuild Layer 3 → Layer 4 gets new stack on next devcontainer rebuild

---

## Current Status (2026-04-23, COMPLETE)

✅ **Layer 1**: layer1-ai-depends published with 6 tag variants (:light, :latest, :playwright_with_chromium/firefox/safari/all) — all building successfully
✅ **Layer 2**: layer2-ai-install published with :claude and :gemini variants — both building successfully
✅ **Layer 3**: All 8 plugin repos migrated to use layer2-ai-install:claude base — all building successfully
✅ **Layer 4**: Project repos (build-with-claude) can reference any Layer 3 plugin container

**Complete Dependency Chain**:
- Layer 1 (layer1-ai-depends) → Layer 2 (layer2-ai-install) → Layer 3 (plugin containers) → Layer 4 (project repos)
- All layers working end-to-end with automatic inheritance of base image updates