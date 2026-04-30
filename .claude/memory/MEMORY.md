# Memory Index

## Project Context
- [project_builder_project_context.md](project_builder_project_context.md) — builder-project dual role: control plane for 4-layer stack + reference project repo
- [project_claude_json_lifecycle.md](project_claude_json_lifecycle.md) — .claude.json and named volume persistence: devcontainerId stability, backup behavior, re-auth conditions
- [user.md](user.md) — GitHub username: sun2admin

## Container Architecture
- [architecture-four-layer-stack.md](architecture-four-layer-stack.md) — Complete 4-layer stack, layer4-devcontainer and project repo concepts, dependency flow, current status
- [layer1-ai-depends-implementation.md](layer1-ai-depends-implementation.md) — layer1-ai-depends: 6 tag variants (playwright_with_all ❌), multi-stage Dockerfile, GitHub Actions matrix
- [layer2-ai-install-implementation.md](layer2-ai-install-implementation.md) — layer2-ai-install: :claude and :gemini variants, conditional Dockerfile

## Devcontainer Behavior
- [devcontainer-implicit-behavior.md](devcontainer-implicit-behavior.md) — VS Code Dev Container implicit behaviors, Docker default capabilities, postStartCommand vs postAttachCommand sequencing
- [devcontainer-volumes-and-mounts.md](devcontainer-volumes-and-mounts.md) — Docker volume and bind mount gotchas, macOS/Docker Desktop file-mount-inside-named-volume issue
- [devcontainer-ssh-and-keys.md](devcontainer-ssh-and-keys.md) — SSH agent forwarding in Dev Containers, loading SSH keys into container-internal agent
- [devcontainer-credential-files.md](devcontainer-credential-files.md) — Pattern for injecting secrets via bind-mounted credential files at /run/credentials/
- [devcontainer-claude-code-auth.md](devcontainer-claude-code-auth.md) — Claude Code auth inside containers, two auth state files, OAuth token refresh, firewall requirements
- [devcontainer-persistence-strategy.md](devcontainer-persistence-strategy.md) — Named volumes + git-committed project config for Claude memory persistence
- [devcontainer-playwright.md](devcontainer-playwright.md) — Baking Playwright into layer1-ai-depends images, multi-stage build, tag variants

## Claude Code Config and Memory
- [claude-code-project-config.md](claude-code-project-config.md) — Auto-discovery of .claude/, CLAUDE.md, .mcp.json from workspace root
- [claude-code-project-discovery-sessions.md](claude-code-project-discovery-sessions.md) — Project discovery based on cwd, ~/.claude/projects structure, session state
- [claude-code-config-loading-precedence.md](claude-code-config-loading-precedence.md) — Config loading: file locations, precedence order
- [claude-code-memory-portability-architecture.md](claude-code-memory-portability-architecture.md) — Memory stored outside repo, why builder-project commits memory to git, best practices
- [claude-code-multi-project-architecture.md](claude-code-multi-project-architecture.md) — Single-project-per-session design, multi-project support pattern
- [init-projects-sync-pattern.md](init-projects-sync-pattern.md) — load-projects.sh seed pattern and sync-prj-repos-memory outbound skill pattern

## Plugin System
- [project-plugin-seed-approach.md](project-plugin-seed-approach.md) — Pre-baking Claude Code plugins into images using CLAUDE_CODE_PLUGIN_CACHE_DIR and CLAUDE_CODE_PLUGIN_SEED_DIR
- [project-plugin-lists.md](project-plugin-lists.md) — Finalized plugin lists: 11 base, 22 coding, 15 external
- [reference-plugins-vs-skills.md](reference-plugins-vs-skills.md) — Plugins (internal to Claude) vs skills (user-invoked slash commands)
- [project-claude-code-actions-placement.md](project-claude-code-actions-placement.md) — claude-code-action and security-review are GitHub Actions (CI only), not container config

## Build Project Design
- [build-project-design-decisions.md](build-project-design-decisions.md) — Core architectural insights for /build-project skill, memory persistence, open questions
- [build-project-skill-clarifications.md](build-project-skill-clarifications.md) — Clarifications on /build-project skill scope and design

## Feedback
- [feedback-auto-commit-on-success.md](feedback-auto-commit-on-success.md) — Auto-commit repo changes after successful implementation
- [feedback-bash-over-zsh.md](feedback-bash-over-zsh.md) — Prefer bash over zsh in Linux devcontainers
- [feedback-check-mounts-first.md](feedback-check-mounts-first.md) — Check existing mounts before creating new directories
- [feedback-credentials-shell-env.md](feedback-credentials-shell-env.md) — Use ~/.profile (chmod 600) for credential env vars, not /etc/environment
- [feedback-ghcr-always-private.md](feedback-ghcr-always-private.md) — All GHCR images must always be private
- [feedback-init-scripts-not-in-image.md](feedback-init-scripts-not-in-image.md) — init-ssh.sh and init-gh-token.sh must never be baked into the container image
- [feedback-new-plugin-layer-output.md](feedback-new-plugin-layer-output.md) — Don't repeat menu options in explanatory text after displaying the menu
- [feedback-new-plugin-layer-prebuilt-repo-verification.md](feedback-new-plugin-layer-prebuilt-repo-verification.md) — Verify GitHub repo/image exists before offering prebuilt
- [feedback-new-plugin-layer-prebuilt-vs-build-separation.md](feedback-new-plugin-layer-prebuilt-vs-build-separation.md) — Separate prebuilt definitions from built images
- [feedback-new-plugin-layer-search-bug.md](feedback-new-plugin-layer-search-bug.md) — Global and marketplace-specific search only query official marketplace
- [feedback-plugins-first-approach.md](feedback-plugins-first-approach.md) — Always default to using available plugins first
- [feedback-sync-always-push.md](feedback-sync-always-push.md) — sync-prj-repos-memory always pushes even if nothing new to commit
- [feedback-use-skill-tool.md](feedback-use-skill-tool.md) — Always use the Skill tool to invoke skills with /skillname syntax
