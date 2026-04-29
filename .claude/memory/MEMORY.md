# Memory Index

## Project Context
- [project_builder_project_context.md](project_builder_project_context.md) — builder-project purpose, 4-layer container architecture, key repos, persistence lifecycle, ongoing work
- [project_claude_json_lifecycle.md](project_claude_json_lifecycle.md) — .claude.json and named volume persistence: devcontainerId stability, backup behavior, re-auth conditions, auto-restore gap
- [user.md](user.md) — GitHub username: sun2admin

## Container Architecture
- [architecture-four-layer-stack.md](architecture-four-layer-stack.md) — Complete 4-layer stack (base-ai-layer, ai-install-layer, plugins, project), dependency flow, current status
- [base-ai-layer-implementation.md](base-ai-layer-implementation.md) — base-ai-layer single Dockerfile with 6 tag variants via ARGs, playwright-builder stage, GitHub Actions matrix
- [ai-install-layer-implementation.md](ai-install-layer-implementation.md) — ai-install-layer Layer 2, :claude and :gemini variants, replaces deprecated claude-install-container
- [plugin-layer-ai-install-migration.md](plugin-layer-ai-install-migration.md) — All 8 plugin repos migrated to ai-install-layer:claude base as of 2026-04-23

## Devcontainer Behavior
- [devcontainer-implicit-behavior.md](devcontainer-implicit-behavior.md) — VS Code Dev Container implicit behaviors, Docker default capabilities, postStartCommand vs postAttachCommand sequencing
- [devcontainer-volumes-and-mounts.md](devcontainer-volumes-and-mounts.md) — Docker volume and bind mount gotchas, macOS/Docker Desktop file-mount-inside-named-volume issue, named volume ownership
- [devcontainer-ssh-and-keys.md](devcontainer-ssh-and-keys.md) — SSH agent forwarding in Dev Containers, loading SSH keys into container-internal agent
- [devcontainer-credential-files.md](devcontainer-credential-files.md) — Pattern for injecting secrets via bind-mounted credential files at /run/credentials/, init script pattern
- [devcontainer-claude-code-auth.md](devcontainer-claude-code-auth.md) — Claude Code auth inside containers, two auth state files, OAuth token refresh, firewall requirements
- [devcontainer-persistence-strategy.md](devcontainer-persistence-strategy.md) — Named volumes + git-committed project config for Claude memory persistence, hybrid approach
- [devcontainer-playwright.md](devcontainer-playwright.md) — Baking Playwright Chromium into devcontainer images, multi-stage build, required env vars

## Claude Code Config and Memory
- [claude-code-project-config.md](claude-code-project-config.md) — Auto-discovery of .claude/, CLAUDE.md, .mcp.json from workspace root, project vs user scope
- [claude-code-project-discovery-sessions.md](claude-code-project-discovery-sessions.md) — Project discovery based on cwd, ~/.claude/projects structure, session state, init-memory.sh seeding pattern
- [claude-code-config-loading-precedence.md](claude-code-config-loading-precedence.md) — Config loading: file locations, precedence order (Managed > CLI > Local > Project > User > Defaults)
- [claude-code-memory-portability-architecture.md](claude-code-memory-portability-architecture.md) — Memory stored in ~/.claude/projects/<path>/memory/ (outside repo, non-portable), why builder-project commits memory to git
- [claude-code-multi-project-architecture.md](claude-code-multi-project-architecture.md) — Single-project-per-session design, /resume for switching, how copying to ~/.claude/projects enables multi-project support
- [init-projects-sync-pattern.md](init-projects-sync-pattern.md) — load-projects.sh seed pattern and sync-prj-repos-memory outbound skill pattern

## Plugin System
- [project-plugin-seed-approach.md](project-plugin-seed-approach.md) — Pre-baking Claude Code plugins into images using CLAUDE_CODE_PLUGIN_CACHE_DIR and CLAUDE_CODE_PLUGIN_SEED_DIR
- [project-plugin-lists.md](project-plugin-lists.md) — Finalized plugin lists: 11 base, 22 coding (6 code flow + 4 dev tooling + 12 LSP), 15 external
- [reference-plugins-vs-skills.md](reference-plugins-vs-skills.md) — Plugins (internal to Claude) vs skills (user-invoked slash commands), how to verify each
- [project-claude-code-actions-placement.md](project-claude-code-actions-placement.md) — claude-code-action and security-review are GitHub Actions (CI only), not container config

## Build Project Design
- [build-project-design-decisions.md](build-project-design-decisions.md) — Core architectural insights for /build-project skill, why memory persistence matters, open questions
- [build-project-skill-clarifications.md](build-project-skill-clarifications.md) — Clarifications on /build-project skill scope and design

## Feedback
- [feedback-auto-commit-on-success.md](feedback-auto-commit-on-success.md) — Auto-commit repo changes after successful implementation, no errors, tests pass
- [feedback-bash-over-zsh.md](feedback-bash-over-zsh.md) — Prefer bash over zsh in Linux devcontainers; bash is pre-installed, Claude Code supports it equally
- [feedback-check-mounts-first.md](feedback-check-mounts-first.md) — Check existing mounts (like /home/claude/data) before creating new directories
- [feedback-credentials-shell-env.md](feedback-credentials-shell-env.md) — Use ~/.profile (chmod 600) for credential env vars, not /etc/environment; use bash --login in postAttachCommand
- [feedback-ghcr-always-private.md](feedback-ghcr-always-private.md) — All GHCR images must always be private unless explicitly stated otherwise
- [feedback-init-scripts-not-in-image.md](feedback-init-scripts-not-in-image.md) — init-ssh.sh and init-gh-token.sh must never be baked into the container image; only init-firewall.sh belongs in the image
- [feedback-new-plugin-layer-output.md](feedback-new-plugin-layer-output.md) — Don't repeat menu options in explanatory text after displaying the menu
- [feedback-new-plugin-layer-prebuilt-repo-verification.md](feedback-new-plugin-layer-prebuilt-repo-verification.md) — Step 7a must verify GitHub repo/image exists before offering prebuilt
- [feedback-new-plugin-layer-prebuilt-vs-build-separation.md](feedback-new-plugin-layer-prebuilt-vs-build-separation.md) — Separate prebuilt definitions (plugin-lists.json) from built images (standards.json)
- [feedback-new-plugin-layer-search-bug.md](feedback-new-plugin-layer-search-bug.md) — Global and marketplace-specific search only query official marketplace, missing other 4 repos
- [feedback-plugins-first-approach.md](feedback-plugins-first-approach.md) — Always default to using available plugins first; only fall back if no suitable plugin exists
- [feedback-use-skill-tool.md](feedback-use-skill-tool.md) — Always use the Skill tool to invoke skills with /skillname syntax, don't manually re-implement the flow
