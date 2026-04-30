# builder-project

Control plane for the 4-layer container stack, and reference AI project repo.

## Two Roles

1. **Control plane** — contains source subdirectories for all 4 container layers. Claude makes changes here and pushes them to each layer's standalone GitHub repo, which triggers that repo's own CI/CD to build and push GHCR images.

2. **Reference project repo** — Claude project files only (CLAUDE.md, .claude/, .mcp.json, memory). Loaded into the running container by a Layer 4 devcontainer repo (e.g. `build-containers-with-claude`) at startup.

## Architecture

4-layer container stack — each layer has its own subdir with a `CLAUDE.md`:

| Layer | Subdir | Standalone Repo | Published Image |
|---|---|---|---|
| Layer 1 | `layer1-ai-depends/` | `sun2admin/layer1-ai-depends` | `ghcr.io/sun2admin/layer1-ai-depends` |
| Layer 2 | `layer2-ai-install/` | `sun2admin/layer2-ai-install` | `ghcr.io/sun2admin/layer2-ai-install:claude\|gemini` |
| Layer 3 | `layer3-ai-plugins/` (docs only) | 8 standalone plugin repos | `ghcr.io/sun2admin/claude-plugins-*` |
| Layer 4 | `layer4-devcontainer/` | e.g. `sun2admin/build-containers-with-claude` | (devcontainer config, no image) |

**Dependency cascade**: Layer 1 → Layer 2 → Layer 3 → Layer 4 inherits automatically on rebuild.

**Layer 3 note**: Plugin repos are currently edited directly in their standalone repos. Consolidation into `layer3-ai-plugins/` is planned.

**Project repos** (e.g. `builder-project`) are separate standalone repos, not part of the container stack. They are cloned by `load-projects.sh` at container start into `/workspace/claude/<name>`.

## Cross-Cutting Rules

- **Shell**: bash only (not zsh)
- **GHCR**: all images must always be private
- **Credentials**: write to `~/.profile` (chmod 600), never `/etc/environment`; use `bash --login` in `postAttachCommand`
- **Container user**: `claude` (bash shell)

## Working Across Layers

**IMPORTANT:** This repo contains multiple architecture layers as subdirectories.

- Before modifying any layer file, explicitly state which layer you are targeting
- If a request could apply to more than one layer, ALWAYS ask which layer before proceeding — never infer from semantic context alone
- When starting work on a layer, declare: "I am working on Layer X" so all follow-up instructions are correctly scoped

## Plan Building

When building a plan with the user:

- After each instruction the user provides, confirm you understand it and ask any clarifying questions before moving on
- Do not proceed to the next step or start execution until the user explicitly says to proceed
- When asking clarifying questions, state how many questions you have remaining and ask them one at a time
