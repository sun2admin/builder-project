---
name: Plugin pre-installation approach for container images using CLAUDE_CODE_PLUGIN_SEED_DIR
description: How to pre-bake Claude Code plugins into container images at build time without running Claude interactively
type: project
---

Claude Code plugins can be pre-installed into container images at build time using `CLAUDE_CODE_PLUGIN_SEED_DIR`. This avoids the need to run Claude interactively or have Anthropic auth at build time.

## Build-time installation

In the Dockerfile (run as the `claude` user):

```dockerfile
ENV CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-plugins

RUN claude plugin marketplace add anthropics/claude-plugins-official && \
 claude plugin install claude-code-setup && \
 claude plugin install hookify
```

Only requires `GH_TOKEN` for GitHub access (not Anthropic auth). The `claude plugin` CLI commands are pure git operations.

## Marketplace must be re-added in every image layer

**Critical:** `claude plugin marketplace add` must be called in each Dockerfile layer that installs plugins. The marketplace configuration written to `~/.claude/settings.json` by a base image is not reliably picked up by `claude plugin install` in a child image layer — even though the file exists. Always run `claude plugin marketplace add anthropics/claude-plugins-official` before any `claude plugin install` calls, in every plugin container Dockerfile.

## example-plugin is not in the marketplace

`example-plugin` exists as a directory in `anthropics/claude-plugins-official` but is **not listed in `.claude-plugin/marketplace.json`**. It cannot be installed via `claude plugin install example-plugin`. Do not include it in any Dockerfile.

## Runtime configuration

Set in the image Dockerfile:
```dockerfile
ENV CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-plugins
```

Claude reads from the seed at startup — no network calls, no prompts. Seed is read-only; auto-updates are disabled for seeded plugins.

## Layering multiple seed dirs

```dockerfile
ENV CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-base-plugins:/opt/claude-coding-plugins
```

Claude searches each directory in order; first match wins.

**Why:** The `/plugin install` command requires Claude to be running. The seed approach pre-bakes everything at image build time, making plugins available instantly with no first-run setup.

**How to apply:** Each plugin image layer installs its plugins to a unique `/opt/` subdirectory and sets `CLAUDE_CODE_PLUGIN_SEED_DIR` to include all parent layer dirs plus its own.