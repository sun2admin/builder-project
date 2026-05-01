# builder-project

Control plane for the 4-layer container stack. Claude makes changes to layer subdirs here and pushes them to each layer's standalone GitHub repo, triggering CI/CD image builds. Also serves as the reference AI project repo — loaded into the running container by a Layer 4 devcontainer repo at startup.

## Architecture

Each layer has its own subdir with a `CLAUDE.md` containing layer-specific detail:

| Layer | Subdir | Standalone Repo | Published Image |
|---|---|---|---|
| Layer 1 | `layer1-ai-depends/` | `sun2admin/layer1-ai-depends` | `ghcr.io/sun2admin/layer1-ai-depends` |
| Layer 2 | `layer2-ai-install/` | `sun2admin/layer2-ai-install` | `ghcr.io/sun2admin/layer2-ai-install:claude\|gemini` |
| Layer 3 | `layer3-ai-plugins/` | 8 standalone plugin repos | `ghcr.io/sun2admin/claude-plugins-*` |
| Layer 4 | `layer4-devcontainer/` | e.g. `sun2admin/build-containers-with-claude` | (devcontainer, no image) |

**Dependency cascade**: Layer 1 → Layer 2 → Layer 3 → Layer 4 inherits on rebuild.

**Project repos** (e.g. `builder-project`) are separate standalone repos cloned at container start — not part of the stack.

## Cross-Cutting Rules

- **Shell**: bash only (not zsh)
- **GHCR**: all images must always be private
- **Credentials**: write to `~/.profile` (chmod 600), never `/etc/environment`; use `bash --login` in `postAttachCommand`
- **Container user**: `claude` (bash shell)
- **Skill creation**: always use the `/skill-creator` plugin when creating or modifying skills

## Working Across Layers

- Before modifying any layer file, explicitly state which layer you are targeting
- If a request could apply to more than one layer, ALWAYS ask which layer before proceeding — never infer from semantic context alone
- When starting work on a layer, declare: "I am working on Layer X"

## Plan Building

- After each instruction, confirm understanding and ask clarifying questions before moving on
- Do not proceed until the user explicitly says to
- State how many questions remain and ask one at a time

## Plugin Usage Policy

- Always check available plugins (MCP servers, skills, and agents) first.
- Utilize relevant plugins, tools, or slash commands to solve tasks instead of attempting to solve them with built-in Bash/Write tools, whenever a plugin is available.
- Prioritize using `/plugin-name:skill` over manual implementation.
