---
name: new-plugin-layer
description: Create a new Claude Code plugin layer container image (Layer 3) on top of ai-install-layer:claude. Use this skill whenever the user wants to build, create, or configure a plugin container image, select plugins for a devcontainer, ask about available plugins, or reference /new-plugin-layer. The skill walks through selecting plugins, detecting duplicates, and generating the GitHub repo + Dockerfile + GitHub Actions workflow needed to build a private GHCR image.
---

# new-plugin-layer

Guides the user through building a new Layer 3 plugin container image. Produces a private GHCR image (`ghcr.io/sun2admin/claude-plugins-<hash>`) that can be referenced in any devcontainer.json.

## Data Files

Read these two files at the start of every invocation:

- `references/standards.json` — already-built images: name, repo, GHCR image path
- `references/plugin-lists.json` — prebuilt plugin selections with full plugin lists and marketplace origins

The marketplace cache files (`.marketplace-*.json`) may already exist in the skill directory from a previous run. Check before fetching.

## Step 1: Initialize Marketplace Cache

Run the cache script to fetch current plugin metadata from all 5 marketplaces:

```bash
bash scripts/init-marketplace-cache.sh
```

Cache files land in the current working directory:
- `.marketplace-claude-plugins-official.json`
- `.marketplace-skills.json`
- `.marketplace-knowledge-work-plugins.json`
- `.marketplace-financial-services-plugins.json`
- `.marketplace-claude-plugins-community.json`

If any fetch fails, note the failure and continue — partial cache is better than stopping.

## Step 2: Show the Selection Menu

Present three paths:

```
Plugin layer options:
  1. Standard  — base / coding / ext / all (Anthropic-defined sets)
  2. Prebuilt  — named custom selections (from plugin-lists.json)
  3. Custom    — browse or search across all 5 marketplaces
```

### Path 1: Standard

Read the four standard entries from `references/standards.json` (type: "standard"). Show name, description, plugin count from `references/plugin-lists.json`. Let the user pick one. Jump to Step 4.

### Path 2: Prebuilt

List all entries from `references/plugin-lists.json` where type is "prebuilt-list" or "custom-build". Show name, description, total plugin count, and whether a built image already exists in `references/standards.json`. If an image exists, offer to return that image reference directly without building. Jump to Step 4.

**Important**: Before offering a prebuilt, verify the GitHub repo actually exists:
```bash
gh repo view sun2admin/<repo-name> --json name -q .name 2>/dev/null
```
Only offer an existing image if the repo is confirmed to exist.

### Path 3: Custom Build

Two sub-options:

**Browse by marketplace** — list available plugins from one or more cache files. Format:
```
claude-plugins-official (42 plugins):
  • plugin-name — short description
  • ...
```

**Search globally** — run the search script:
```bash
bash scripts/plugin-search.sh "<search-term>" .
```
This searches name and description fields across all 5 cached marketplaces. Show results grouped by marketplace.

Let the user add plugins iteratively. Show a running tally after each addition:
```
Selected (5): claude-code-setup, skill-creator, code-review, pr-review-toolkit, feature-dev
```

## Step 3: Confirm Selection

Show the final plugin list grouped by marketplace. Ask the user to confirm before proceeding.

## Step 4: Deduplication Check

Generate a hash from the sorted plugin names:
```bash
echo -n "<sorted-comma-separated-plugin-names>" | sha256sum | cut -c1-8
```

Check if this hash appears in `references/standards.json` (repo names follow the pattern `claude-plugins-<hash>`). If a match exists and the repo is confirmed to exist, tell the user:

> "This exact plugin selection already exists as `ghcr.io/sun2admin/claude-plugins-<hash>:latest`. Use this image in your devcontainer.json."

No build needed. Done.

## Step 5: Build a New Image

If no duplicate exists, proceed to build.

**Repo and image names:**
- Repo: `claude-plugins-<8char-hash>`
- Image: `ghcr.io/sun2admin/claude-plugins-<8char-hash>`

**Create the GitHub repo (private):**
```bash
gh repo create sun2admin/claude-plugins-<hash> --private --description "Claude Code plugin layer: <description>"
```

**Generate three files** in a local temp directory, then push to the repo:

### Dockerfile

```dockerfile
FROM ghcr.io/sun2admin/ai-install-layer:claude

# Plugin layer: <description>
# Plugins (<count>): <comma-separated names>

ARG CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-custom-plugins
ENV CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-custom-plugins

# Install plugins at build time
RUN --mount=type=cache,target=/root/.npm \
    CLAUDE_CODE_PLUGIN_CACHE_DIR=${CLAUDE_CODE_PLUGIN_CACHE_DIR} \
    <for each marketplace source>
    claude plugin marketplace add <source-url> && \
    </for each marketplace source>
    <for each plugin>
    claude plugin install <plugin-name> && \
    </for each plugin>
    echo "Plugins installed"

RUN mkdir -p ${CLAUDE_CODE_PLUGIN_CACHE_DIR} && \
    chown -R claude:claude ${CLAUDE_CODE_PLUGIN_CACHE_DIR}
```

Marketplace source URLs:
- `claude-plugins-official` → `https://github.com/anthropics/claude-plugins-official`
- `anthropics/skills` → `https://github.com/anthropics/skills`
- `anthropics/knowledge-work-plugins` → `https://github.com/anthropics/knowledge-work-plugins`
- `anthropics/financial-services-plugins` → `https://github.com/anthropics/financial-services-plugins`
- `anthropics/claude-plugins-community` → `https://github.com/anthropics/claude-plugins-community`

Only add `claude plugin marketplace add` for marketplaces that have plugins in this selection.

### manifest.json

```json
{
  "name": "claude-plugins-<hash>",
  "description": "<user description>",
  "base_image": "ghcr.io/sun2admin/ai-install-layer:claude",
  "plugins": [
    {"name": "<plugin>", "marketplace": "<marketplace>"}
  ],
  "distribution": {
    "<marketplace>": <count>
  },
  "created": "<ISO date>"
}
```

### .github/workflows/build-and-push.yml

Generate a GitHub Actions workflow that:
- Triggers on push to main (when Dockerfile changes)
- Logs in to GHCR using `secrets.GITHUB_TOKEN`
- Builds and pushes `ghcr.io/sun2admin/claude-plugins-<hash>:latest`
- Sets the image visibility to **private** after push

Use this pattern for the workflow structure (adapt as needed):
```yaml
name: Build and Push Plugin Image
on:
  push:
    branches: [main]
    paths: [Dockerfile]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/sun2admin/claude-plugins-<hash>:latest
      - name: Set image private
        run: |
          gh api \
            --method PATCH \
            /user/packages/container/claude-plugins-<hash>/visibility \
            -f visibility=private
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Step 6: Push and Trigger Build

Push the three files to the repo and trigger the workflow:
```bash
gh workflow run build-and-push.yml --repo sun2admin/claude-plugins-<hash>
```

## Step 7: Update standards.json

Add the new entry to `references/standards.json`:
```json
{
  "name": "<user-provided-name-or-hash>",
  "description": "<description>",
  "type": "custom-build",
  "repo": "claude-plugins-<hash>",
  "image": "ghcr.io/sun2admin/claude-plugins-<hash>"
}
```

Also add the full plugin selection to `references/plugin-lists.json` so it can be offered as a prebuilt in future runs.

## Step 8: Return the Result

Tell the user:
> "Build triggered. Once the GitHub Actions workflow completes (~5 min), use this in your devcontainer.json:
> `ghcr.io/sun2admin/claude-plugins-<hash>:latest`"

Show the GitHub Actions URL so they can watch the build.

## Key Constraints

- All GHCR images **must** be private — enforce this in the workflow and after push
- Base image is always `ghcr.io/sun2admin/ai-install-layer:claude` — never change this
- Do not modify the four `type: "standard"` entries in `references/standards.json`
- Identical plugin selections must reuse the existing image (hash-based deduplication)
- Only add marketplace sources for marketplaces actually used in the selection
