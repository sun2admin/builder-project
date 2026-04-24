---
name: Plugin Layer Migration to ai-install-layer
description: Completed migration of all 8 plugin repos from deprecated claude-install-container to ai-install-layer:claude base image (deleted 2026-04-24)
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Completed Migration

All 8 plugin layer repositories have been updated to use `ghcr.io/sun2admin/ai-install-layer:claude` as their base image instead of `ghcr.io/sun2admin/claude-install-container:latest`.

### Repos Migrated

**All 8 Plugin Repos Updated:**
1. ✅ `claude-anthropic-base-plugins-container` — Dockerfile updated, build successful
2. ✅ `claude-anthropic-coding-plugins-container` — Dockerfile updated, build successful
3. ✅ `claude-anthropic-ext-plugins-container` — Dockerfile updated, build successful
4. ✅ `claude-anthropic-all-plugins-container` — Dockerfile updated, build successful
5. ✅ `claude-plugins-34e199d2` — Dockerfile + workflow matrix fixed, rebuilding
6. ✅ `claude-plugins-3f889e47` — Dockerfile + workflow matrix fixed, rebuilding
7. ✅ `claude-plugins-54ca621f` — Dockerfile updated, build successful
8. ✅ `claude-plugins-a7f3d2e8` — Dockerfile updated, build successful

### Changes Made

**Dockerfile Updates (all repos):**
- Changed: `ARG BASE_IMAGE=ghcr.io/sun2admin/claude-install-container:latest`
- To: `ARG BASE_IMAGE=ghcr.io/sun2admin/ai-install-layer:claude`

**Workflow Matrix Fixes (repos 5 & 6 only):**
- Removed: `playwright` tag variant (does not exist in ai-install-layer)
- Updated: `latest` base from `claude-install-container:latest` to `ai-install-layer:claude`
- Repos affected: claude-plugins-34e199d2, claude-plugins-3f889e47

### Current Status (2026-04-23, COMPLETE)

✅ **ALL 8 REPOS BUILDING SUCCESSFULLY**

### Root Cause Analysis & Fixes Applied

**3f889e47 (e47):**
- **Problem**: Plugin manifest listed 10 non-existent plugins from anthropics/skills marketplace (ai-safety, custom-workflows, data-analysis, etc.)
- **Fix**: Updated manifest and Dockerfile to only include `document-skills@anthropic-agent-skills` (the only valid plugin from that marketplace)
- **Validation**: Confirmed anthropics/skills marketplace only has valid plugins like skill-creator, frontend-design, mcp-builder, etc. — none of the originally-listed ones existed

**34e199d2 (d2):**
- **Problem**: Plugin manifest referenced external plugins from "anthropics/claude-plugins-community" which doesn't exist as a marketplace
- **Fix**: Changed marketplace reference to "anthropics/claude-plugins-official" where external_plugins directory actually contains asana, context7, discord, firebase, github, gitlab, greptile, imessage, laravel-boost, linear, playwright, serena, telegram, terraform
- **Validation**: Confirmed external_plugins/ directory exists in anthropics/claude-plugins-official repo with all 15 external plugins

### Final Build Status (2026-04-23 16:16 UTC)
- ✅ claude-anthropic-base-plugins-container (success)
- ✅ claude-anthropic-coding-plugins-container (success)
- ✅ claude-anthropic-ext-plugins-container (success)
- ✅ claude-anthropic-all-plugins-container (success)
- ✅ claude-plugins-34e199d2 (success) — **FIXED**
- ✅ claude-plugins-3f889e47 (success) — **FIXED**
- ✅ claude-plugins-54ca621f (success)
- ✅ claude-plugins-a7f3d2e8 (success)

### GHCR Permissions

All plugin repos are private. The user manually granted read access on:
- `base-ai-layer` → all ai-install-layer and plugin repos
- `ai-install-layer` → all plugin repos

This allows proper image pulling during multi-layer builds.

### Next Steps

Once both rebuilds complete:
1. Verify all 8 repos show successful builds
2. Confirm devcontainer references still point to layer 3 (plugins layer) correctly
3. Project repos (layer 4) can now reference updated plugin layers without code changes

---

**Date**: 2026-04-23
**Status**: ✅ Complete — All 8 repos building successfully with ai-install-layer:claude base
