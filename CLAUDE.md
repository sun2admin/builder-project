# builder-project

Reference Layer 4 Part 2 Claude project and single repo for all container layer sources.

## Architecture

4-layer container stack — each layer is a subdirectory with its own `CLAUDE.md`:

| Layer | Subdir | Published Image |
|---|---|---|
| Layer 1 | `layer1-ai-depends/` | `ghcr.io/sun2admin/layer1-ai-depends` |
| Layer 2 | `layer2-ai-install/` | `ghcr.io/sun2admin/layer2-ai-install:claude` |
| Layer 3 | `layer3-ai-plugins/` | `ghcr.io/sun2admin/claude-plugins-*` |
| Layer 4 Part 1 | `layer4-part1/` | devcontainer config + init scripts |
| Layer 4 Part 2 | *(this repo root)* | Claude project files — CLAUDE.md, .claude/, .mcp.json |

**Dependency cascade**: Layer 1 → Layer 2 → Layer 3 → Layer 4 inherits automatically on rebuild.

**Layer 4 Part 2 repos** are separate standalone GitHub repos cloned by `load-projects.sh` at container start into `/workspace/claude/<name>`. They are not subdirectories here.

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
