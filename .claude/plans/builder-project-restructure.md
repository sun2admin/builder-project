# Plan: builder-project Directory Restructure

## Goal
Align builder-project with Anthropic best practices: slim CLAUDE.md, create modular
rules files per layer, and correctly reflect the Layer 4 Part 2 role of this repo.

---

## Step 1: Slim CLAUDE.md

**Keep** (~20 lines total):
- Project purpose (1–2 sentences)
- 4-layer architecture diagram + dependency chain
- Pointer to nested CLAUDE.md files for layer detail
- Cross-cutting rules: GHCR always private, bash not zsh
- Layer disambiguation rule: before modifying any layer file, state which layer is targeted;
  if a request could apply to more than one layer, always ask before proceeding;
  never infer target layer from semantic context alone
- Session discipline pattern: explicitly declare "I am working on Layer X" before giving
  layer-specific instructions, so vague follow-ups are correctly scoped

**Remove** (moves to rule files):
- Init scripts table → `layer-4-part1.md`
- Credentials section → `layer-4-part1.md`
- Shell section → `cross-layer.md`
- MCP section → `layer-4-part1.md` + `layer-4-part2.md`
- GitHub Actions section → `layer-4-part1.md`

---

## Step 2: Create .claude/rules/ Files

Six files, **path-scoped** (`paths:` frontmatter) — all layers are subdirectories within
this single repo, so rules fire automatically when Claude opens files in each layer's dir.

### `layer-1-base-ai.md`
- Path scope: `layer1/**` (or whatever the actual subdir name is — TBD)
- What it builds: system packages, Python, graphics libs, Playwright
- Tag variants: `:light`, `:latest`, `:playwright_with_*`
- Dockerfile ARG structure (INCLUDE_EXTRAS, INCLUDE_PLAYWRIGHT, BROWSERS)
- GitHub Actions matrix: 6 variants in parallel

### `layer-2-ai-install.md`
- Path scope: `layer2/**` (subdir name TBD)
- Builds FROM base-ai-layer:latest
- Tag variants: `:claude`, `:gemini`
- Single Dockerfile with conditional ARG logic (AI_TYPE, AI_PACKAGE, USERNAME)
- GitHub Actions matrix: 2 variants in parallel

### `layer-3-plugins.md`
- Path scope: `layer3/**` (subdir name TBD)
- 8 plugin variants: claude-anthropic-{base,coding,ext,all}-plugins-container + 4 custom
- All build FROM ai-install-layer:claude
- Plugin baking: CLAUDE_CODE_PLUGIN_CACHE_DIR + CLAUDE_CODE_PLUGIN_SEED_DIR
- Marketplace sources: anthropics/claude-plugins-official, anthropics/skills
- Key constraint: all GHCR images must be private

### `layer-4-part1.md`
- Path scope: `layer4-part1/**` (subdir name TBD)
- Role: container/dependency layer — shaped by what Part 2 repos need
- devcontainer.json references Layer 3 image
- Init scripts: init-firewall.sh (sudo/iptables), init-ssh.sh, init-gh-token.sh, init-github-mcp.sh
- load-projects.sh: clones Part 2 repos into /workspace/<ai-name>/<repo-name> at container start
- Credentials via bind-mounted /run/credentials/ files
- postStartCommand sequence, postAttachCommand uses bash --login
- Note: see layer4-design.md for planned migration of init scripts to Part 2 repos

### `layer-4-part2.md`
- Always-loaded (no paths: frontmatter) — Part 2 repos are separate standalone repos,
  not subdirectories of builder-project; no local files to trigger path-scoped loading
- Documents the Part 2 pattern: builder-project is the reference implementation
- Role: standalone Claude/AI project repo, cloned by load-projects.sh into the container
- Self-contained and portable — usable outside the 4-layer architecture entirely
- Contains only Claude files: CLAUDE.md, .claude/, .mcp.json, skills, memory
- Cloned to /workspace/<ai-name>/<repo-name> — only one AI workspace at a time
- SessionStart hook: adds $CLAUDE_PROJECT_DIR/scripts/bin to PATH via $CLAUDE_ENV_FILE
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
