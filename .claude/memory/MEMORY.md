# Project Memory Index

This directory contains persistent learnings from development sessions in this workspace.

## Files

### [devcontainer-ssh-and-keys.md](devcontainer-ssh-and-keys.md)
SSH agent forwarding behavior in VS Code Dev Containers, and how to load SSH keys into a container-internal agent. Covers implicit `SSH_AUTH_SOCK` forwarding, how to override it, and the pattern for mounting/copying private keys securely at startup.

### [devcontainer-volumes-and-mounts.md](devcontainer-volumes-and-mounts.md)
Docker volume and bind mount gotchas in Dev Containers. Covers the macOS/Docker Desktop file-mount-inside-named-volume reliability issue, the neutral staging path workaround, named volume ownership problems, and how to force a full Docker image cache rebuild.

### [devcontainer-claude-code-auth.md](devcontainer-claude-code-auth.md)
How Claude Code authentication works inside containers. Covers the two auth state files, why `hasCompletedOnboarding` cannot be pre-seeded, OAuth token refresh behavior, firewall requirements, and the trade-offs between per-container vs. shared named volumes for the `~/.claude` directory.

### [devcontainer-implicit-behavior.md](devcontainer-implicit-behavior.md)
VS Code Dev Containers implicit/automatic behaviors that require no devcontainer.json config, Docker's default capability set, container shutdown reliability notes, `postStartCommand` vs `postAttachCommand` sequencing, iptables/firewall runtime requirements, and the /workspace VS Code convention.

### [devcontainer-playwright.md](devcontainer-playwright.md)
How to bake Playwright Chromium into a devcontainer image using a multi-stage build. Covers the playwright-builder stage, required env vars (PLAYWRIGHT_CHROMIUM_SANDBOX, PLAYWRIGHT_BROWSERS_PATH), and runtime system dependencies.

### [devcontainer-credential-files.md](devcontainer-credential-files.md)
Pattern for injecting secrets into containers via bind-mounted credential files. Covers the /run/credentials/ staging path, current credentials (SSH key, GitHub PAT), init script pattern, and how GH_TOKEN is written to /home/claude/.profile (chmod 600).

### [devcontainer-persistence-strategy.md](devcontainer-persistence-strategy.md)
Why named volumes + git-committed project config is correct for Claude memory/config persistence. Covers the ephemeralness problem, hybrid approach (named volume + repo + init-memory.sh seed-on-start), `CLAUDE_CONFIG_DIR` env var, and why this is better than alternatives. Foundation for /build-project skill.

### [claude-code-project-config.md](claude-code-project-config.md)
How Claude Code auto-discovers project-level config (.claude/, CLAUDE.md, .mcp.json) from the workspace root — no symlinks or copying needed. Covers project vs user scope for skills, commands, agents, MCP, memory, and config precedence order.

### [claude-code-project-discovery-sessions.md](claude-code-project-discovery-sessions.md)
How Claude Code discovers projects based on working directory (cwd), manages session state and auto-memory across restarts/rebuilds, and how containerized setups differ. Covers working directory detection, ~/.claude/projects structure, init-memory.sh seeding pattern, and multi-project workspace support.

### [claude-code-config-loading-precedence.md](claude-code-config-loading-precedence.md)
Complete config loading process: file locations searched, precedence order (Managed > CLI > Local > Project > User > Defaults), how CLAUDE.md and settings.json merge, and defaults for model, permissions, auto-memory. Includes practical examples of config resolution and how multi-project workspaces avoid collisions.

### [claude-code-memory-portability-architecture.md](claude-code-memory-portability-architecture.md)
Critical insight: Claude stores project state in ~/.claude/projects/<path>/memory/ (outside project repo, non-portable, machine-specific). Explains the drawback: memory lost across machines/rebuilds. Explains why build-with-claude commits memory to git. Best practices: init-memory.sh seed pattern + sync-memory skill. Multi-layer memory system: git → named volume → auto-memory → git.

### [build-project-design-decisions.md](build-project-design-decisions.md)
Core architectural insights for /build-project skill. Why memory persistence matters (compound learning, team knowledge), why build-with-claude's patterns work, what it demonstrates successfully, assumptions for /build-project design, open questions about project types/addons/multi-project support.

### [claude-code-multi-project-architecture.md](claude-code-multi-project-architecture.md)
How Claude Code fundamentally handles multiple projects: single-project-per-session design, /resume command for switching between projects, global context in ~/.claude, how copying all projects to ~/.claude/projects/ enables seamless multi-project support. No explicit project selection needed — /resume discovers all projects automatically.

### [architecture-four-layer-stack.md](architecture-four-layer-stack.md)
Complete container architecture: Layer 1 (base-ai-layer: :light, :latest, :playwright_with_*), Layer 2 (ai-install-layer: :claude, :gemini), Layer 3 (ai-plugins containers with pre-baked plugins), Layer 4 (project repos). Dependency flow, current status, next steps.

### [base-ai-layer-implementation.md](base-ai-layer-implementation.md)
base-ai-layer single Dockerfile with conditional builds for 6 tag variants via ARGs. playwright-builder stage, mkdir workaround for empty BROWSERS, --break-system-packages, GitHub Actions matrix build, all 6 variants tested successfully 2026-04-23.

### [ai-install-layer-implementation.md](ai-install-layer-implementation.md)
ai-install-layer Layer 2 with conditional Dockerfile for :claude and :gemini variants. Replaces deprecated claude-install-container (deleted 2026-04-24). GitHub Actions matrix builds both variants in parallel.

### [plugin-layer-ai-install-migration.md](plugin-layer-ai-install-migration.md)
Migration complete: all 8 plugin repos updated to use ai-install-layer:claude base. Fixed workflow matrix for 2 repos (removed playwright variant, updated base image). All repos building successfully as of 2026-04-23.

### [project-claude-code-actions-placement.md](project-claude-code-actions-placement.md)
claude-code-action and claude-code-security-review are GitHub Actions (CI only), not container config — added via /new-code-prj skill to software dev project repos only.

### [project-plugin-seed-approach.md](project-plugin-seed-approach.md)
How to pre-bake Claude Code plugins into container images at build time using CLAUDE_CODE_PLUGIN_CACHE_DIR and CLAUDE_CODE_PLUGIN_SEED_DIR. No Anthropic auth needed — only GH_TOKEN. Layering multiple seed dirs with colon-separated paths.

### [project-plugin-lists.md](project-plugin-lists.md)
Finalized plugin lists per container layer: 11 base plugins, 22 coding plugins (6 code flow + 4 dev tooling + 12 LSP), 15 external plugins. Includes rationale for hookify in base and LSP size warning.

### [reference-plugins-vs-skills.md](reference-plugins-vs-skills.md)
Claude plugins (e.g. code-review) are different from Claude Code skills (e.g. /review). Plugins are used internally by Claude during task execution; skills are user-invoked slash commands. How to verify each with `claude plugin list` vs `/help`.

### [feedback-init-scripts-not-in-image.md](feedback-init-scripts-not-in-image.md)
Feedback: init-ssh.sh and init-gh-token.sh must never be baked into the container image. Only init-firewall.sh belongs in the image.

### [feedback-ghcr-always-private.md](feedback-ghcr-always-private.md)
Feedback: All GHCR images must always be private unless explicitly stated otherwise.

### [feedback-credentials-shell-env.md](feedback-credentials-shell-env.md)
Feedback: Use ~/.profile (chmod 600) for credential env vars in devcontainers, not /etc/environment (world-readable) or .bashrc (not sourced by subprocesses). Use `bash --login -c '...'` in postAttachCommand so .profile is sourced. Use sed-before-append to avoid duplicate entries on restart.

### [feedback-bash-over-zsh.md](feedback-bash-over-zsh.md)
Feedback: Prefer bash over zsh in Linux devcontainers. zsh requires explicit installation, zsh-in-docker, and adds shell config complexity. bash is pre-installed, uses standard /etc/skel files, and Claude Code supports it equally.

### [feedback-new-plugin-layer-output.md](feedback-new-plugin-layer-output.md)
Don't repeat menu options in explanatory text after displaying the menu. Show menu, ask for input directly.

### [feedback-new-plugin-layer-search-bug.md](feedback-new-plugin-layer-search-bug.md)
Global and marketplace-specific search only query the official marketplace, missing results from other 4 repos.

### [feedback-use-skill-tool.md](feedback-use-skill-tool.md)
Always use the Skill tool to invoke skills with /skillname syntax, don't manually re-implement the flow.

### [feedback-new-plugin-layer-prebuilt-repo-verification.md](feedback-new-plugin-layer-prebuilt-repo-verification.md)
Step 7a must verify GitHub repo/image actually exists before offering prebuilt, not assume existence based on standards.json entry.

### [feedback-new-plugin-layer-prebuilt-vs-build-separation.md](feedback-new-plugin-layer-prebuilt-vs-build-separation.md)
Separate prebuilt definitions (plugin-lists.json) from built images (standards.json). Prebuilt names and built repo names should not conflict.

### [feedback-auto-commit-on-success.md](feedback-auto-commit-on-success.md)
Auto-commit repo changes after successful implementation — no errors, tests pass, feature works. Keep repo state current.

### [feedback-plugins-first-approach.md](feedback-plugins-first-approach.md)
Always default to using available plugins first for relevant tasks. Plugins are pre-baked to be the primary approach — only fall back to alternatives if no suitable plugin exists.

### [feedback-check-mounts-first.md](feedback-check-mounts-first.md)
Check existing mounts (like /home/claude/data) before creating new directories. Use existing mounts for persistent output instead of creating parallel directories in /workspace/.

### [user.md](user.md)
GitHub username: sun2admin

## Last Updated
2026-04-24 (Claude Code project discovery research added)
