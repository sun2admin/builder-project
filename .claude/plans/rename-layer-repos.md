# Plan: Rename Layer Repos to layer1-ai-depends / layer2-ai-install

## Goal
Replace `base-ai-layer` and `ai-install-layer` naming with `layer1-ai-depends` and
`layer2-ai-install` across all repos and references. Old repos (`base-ai-layer`,
`ai-install-layer`) are left untouched — do not archive, delete, or modify them.

---

## Image Build Status

### layer1-ai-depends (ghcr.io/sun2admin/layer1-ai-depends)

| Variant | Status |
|---|---|
| `:light` | ✅ Built and pushed |
| `:latest` | ✅ Built and pushed |
| `:playwright_with_chromium` | ✅ Built and pushed |
| `:playwright_with_firefox` | ✅ Built and pushed |
| `:playwright_with_safari` | ✅ Built and pushed |
| `:playwright_with_all` | ❌ Exceeds GitHub Actions runner time limit — do not attempt rebuild |

### layer2-ai-install (ghcr.io/sun2admin/layer2-ai-install)

| Variant | Status |
|---|---|
| `:claude` | ✅ Built and pushed |
| `:gemini` | ✅ Built and pushed |

---

## Steps

### Step 1: Fix local layer2-ai-install/Dockerfile in builder-project ❌
- File: `layer2-ai-install/Dockerfile`
- Change: `BASE_IMAGE=ghcr.io/sun2admin/base-ai-layer:latest`
       → `BASE_IMAGE=ghcr.io/sun2admin/layer1-ai-depends:latest`
- Commit and push to builder-project

### Step 2: Update all 8 plugin repos to use layer2-ai-install:claude ❌
Each repo currently has `BASE_IMAGE=ghcr.io/sun2admin/ai-install-layer:claude`.
Update to `BASE_IMAGE=ghcr.io/sun2admin/layer2-ai-install:claude` and push to trigger rebuild.

Repos to update:
- [ ] `sun2admin/claude-anthropic-base-plugins-container`
- [ ] `sun2admin/claude-anthropic-coding-plugins-container`
- [ ] `sun2admin/claude-anthropic-ext-plugins-container`
- [ ] `sun2admin/claude-anthropic-all-plugins-container`
- [ ] `sun2admin/claude-plugins-a7f3d2e8`
- [ ] `sun2admin/claude-plugins-3f889e47`
- [ ] `sun2admin/claude-plugins-34e199d2`
- [ ] `sun2admin/claude-plugins-54ca621f`

### Step 3: Update memory files ❌
12 memory files still reference old names. Update to use new names:
- `base-ai-layer` → `layer1-ai-depends`
- `ai-install-layer` → `layer2-ai-install`
- `ghcr.io/sun2admin/base-ai-layer` → `ghcr.io/sun2admin/layer1-ai-depends`
- `ghcr.io/sun2admin/ai-install-layer` → `ghcr.io/sun2admin/layer2-ai-install`

Files:
- `architecture-four-layer-stack.md`
- `ai-install-layer-implementation.md` (rename file too → `layer2-ai-install-implementation.md`)
- `base-ai-layer-implementation.md` (rename file too → `layer1-ai-depends-implementation.md`)
- `build-project-skill-clarifications.md`
- `build-project-design-decisions.md`
- `MEMORY.md`
- `claude-code-project-discovery-sessions.md`
- `init-projects-sync-pattern.md`
- `claude-code-memory-portability-architecture.md`
- `devcontainer-playwright.md`
- `plugin-layer-ai-install-migration.md`
- `project_builder_project_context.md`

---

## Constraints

- `base-ai-layer` and `ai-install-layer` GitHub repos — leave completely untouched
- All GHCR images must remain private
- Plugin repo image builds must succeed before Step 3 memory updates are considered complete

---

## Status
- [x] layer1-ai-depends GitHub repo created, workflow updated, 5/6 images built
- [x] layer2-ai-install GitHub repo created, workflow updated, both images built
- [x] builder-project subdirs renamed (base-ai-layer/ → layer1-ai-depends/, ai-install-layer/ → layer2-ai-install/)
- [ ] Step 1: Fix local layer2-ai-install/Dockerfile BASE_IMAGE reference
- [ ] Step 2: Update 8 plugin repos and rebuild images
- [ ] Step 3: Update memory files
