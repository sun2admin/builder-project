# Plan: builder-project Directory Restructure

## Goal
Align builder-project with Anthropic best practices: slim CLAUDE.md, create modular
rules files per layer, and correctly reflect the Layer 4 Part 2 role of this repo.

---

## Step 1: Slim CLAUDE.md

**Keep** (~20 lines total):
- Project purpose (1–2 sentences)
- 4-layer architecture diagram + dependency chain
- Pointer to `.claude/rules/` for layer detail
- Cross-cutting rules: GHCR always private, bash not zsh

**Remove** (moves to rule files):
- Init scripts table → `layer-4-part1.md`
- Credentials section → `layer-4-part1.md`
- Shell section → `cross-layer.md`
- MCP section → `layer-4-part1.md` + `layer-4-part2.md`
- GitHub Actions section → `layer-4-part1.md`

---

## Step 2: Create .claude/rules/ Files

Six files, always-loaded (no `paths:` frontmatter — layers 1–3 are external repos,
no local files to trigger path-scoped loading).

### `layer-1-base-ai.md`
- Repo: `sun2admin/base-ai-layer`
- What it builds: system packages, Python, graphics libs, Playwright
- Tag variants: `:light`, `:latest`, `:playwright_with_*`
- Dockerfile ARG structure (INCLUDE_EXTRAS, INCLUDE_PLAYWRIGHT, BROWSERS)
- GitHub Actions matrix: 6 variants in parallel

### `layer-2-ai-install.md`
- Repo: `sun2admin/ai-install-layer`
- Builds FROM base-ai-layer:latest
- Tag variants: `:claude`, `:gemini`
- Single Dockerfile with conditional ARG logic (AI_TYPE, AI_PACKAGE, USERNAME)
- GitHub Actions matrix: 2 variants in parallel

### `layer-3-plugins.md`
- 8 plugin repos: claude-anthropic-{base,coding,ext,all}-plugins-container + 4 custom
- All build FROM ai-install-layer:claude
- Plugin baking: CLAUDE_CODE_PLUGIN_CACHE_DIR + CLAUDE_CODE_PLUGIN_SEED_DIR
- Marketplace sources: anthropics/claude-plugins-official, anthropics/skills
- Key constraint: all GHCR images must be private

### `layer-4-part1.md`
- Repos: build-with-claude, build-with-claude-stage2, build-with-claude-stage3
- Role: container/dependency layer — shaped by what Part 2 needs
- devcontainer.json references Layer 3 image
- Init scripts: init-firewall.sh (sudo/iptables), init-ssh.sh, init-gh-token.sh, init-github-mcp.sh
- Credentials via bind-mounted /run/credentials/ files
- postStartCommand sequence, postAttachCommand uses bash --login
- update-github-mcp.yml: weekly GitHub Action to update MCP binary (identical across all 3 repos)
- Note: see layer4-design.md for planned migration of scripts to Part 2

### `layer-4-part2.md`
- This repo (builder-project) is the reference implementation
- Role: Claude project repo — self-contained and portable, usable outside 4-layer architecture
- Contains only Claude files: CLAUDE.md, .claude/, .mcp.json, skills, memory
- Cloned to /workspace/<ai-name>/<repo-name> — only one AI workspace at a time
- SessionStart hook: adds $CLAUDE_PROJECT_DIR/scripts/bin to PATH via $CLAUDE_ENV_FILE
  (enables project-local binaries without Part 1 involvement)
- .mcp.json uses relative path for MCP binary (./scripts/bin/...) — confirmed working
- Note: see layer4-design.md for planned migration of init scripts and binaries to Part 2

### `cross-layer.md`
- Shell: bash only (not zsh) — bash is pre-installed, Claude Code supports it equally
- GHCR: all images must always be private
- Credentials: use ~/.profile (chmod 600), not /etc/environment; bash --login in postAttachCommand
- Dependency cascade: update Layer 1 → rebuild Layer 2 → rebuild Layer 3 → Layer 4 auto-inherits
- Container user: `claude` (bash shell)

---

## Step 3: Clean Up

- Remove `.gitkeep` from `.claude/rules/` once rule files are added
- Verify CLAUDE.md stays under 25 lines after slim-down

---

## Status
- [x] SessionStart hook added (session-start.sh + settings.json)
- [ ] CLAUDE.md not yet slimmed
- [ ] Rule files not yet created
- [ ] Ready to implement
