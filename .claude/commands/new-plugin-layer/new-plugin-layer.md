# new-plugin-layer

Create a new Claude Code plugin layer image on top of `ai-install-layer:claude`. Produces a private GHCR image that can be referenced in any project's `devcontainer.json`.

## Usage

```
/new-plugin-layer
```

---

## Steps

### 1. Load standards and plugin lists

- [ ] Read `./standards.json` — metadata for standard builds
- [ ] Read `./plugin-lists.json` — complete plugin lists with marketplace origins for each prebuilt
- [ ] Parse both and maintain in session state (this data persists throughout the skill execution for proper state tracking)

**State tracking initialization:**
- Initialize selections map: `{ marketplace_repo → Set<plugin_name> }` (all empty at start)
- When a prebuilt is selected (Step 3c or Step 3a), populate this map using `plugin-lists.json` distribution data
- This ensures accurate marketplace-specific selection counts at all times

### 2. Fetch marketplace plugin lists

Fetch the available plugins from all five marketplaces. For each, get the marketplace name (from its `marketplace.json` `name` field) and the full plugin list:

| Marketplace repo | Owner | Warning |
|---|---|---|
| `anthropics/claude-plugins-official` | Anthropic | — |
| `anthropics/skills` | Anthropic | — |
| `anthropics/knowledge-work-plugins` | Anthropic | — |
| `anthropics/financial-services-plugins` | Anthropic | — |
| `anthropics/claude-plugins-community` | 3rd Party | ⚠️ Community-submitted, minimal vetting |

For each marketplace repo fetch:
- `bash ./scripts/plugin-search.sh "*" "."` → get all plugins from marketplace cache (uses `.marketplace-*.json` cache files from init-marketplace-cache.sh)
- For each plugin, extract:
  - `name` (identifier)
  - `description` (summary)
  - `category` (if present, for Step 5a categorization)
  - `skills` array (sub-skills/components, if present — used in Step 3a-plugins)
  - `source.url` (GitHub repo for size calculation)
- Cache all results (plugins, skills, and sizes) in memory for the session
- Use `plugin-lists.json` as source of truth for prebuilt plugin membership and marketplace origins

### 3. Show main menu

Display menu with options for existing builds, custom builds, and no plugins:

```
Plugin Layer Builder
════════════════════════════════════════

  [E] Select existing build
  [C] Build custom
  [N] No plugins (use ai-install-layer:claude directly)
  [Q] Quit

Select an option:
```

- `[E]` → continue to Step 3a (existing builds submenu)
- `[C]` → continue to Step 3b (custom build options submenu)
- `[N]` → go to Step 9 with `ghcr.io/sun2admin/ai-install-layer:claude` — no repo creation needed
- `[Q]` → exit the skill immediately with no changes made

### 3a. Existing builds submenu

Show all standard builds from `standards.json` with descriptions, plugin counts, estimated sizes, repo names, and image references:

```
Select Existing Build
═══════════════════════════════════════════════════════════════════════════════════════════════════════

These are pre-built plugin images ready to use. Select one to use as-is, or view plugins first.

  Build               Plugins  Size    Description                    Repo                                    Image
  ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  [1] base            10       ~8MB    General-purpose plugins        claude-anthropic-base-plugins-container           base:latest
  [2] coding          32       ~35MB   Base + software development    claude-anthropic-coding-plugins-container         coding:latest
  [3] ext             25       ~35MB   Base + external/third-party    claude-anthropic-ext-plugins-container            ext:latest
  [4] all             47       ~47MB   Base + coding + external       claude-anthropic-all-plugins-container            all:latest
  [5] base-ext-skills 26       ~37MB   Custom build (34e199d2)        claude-plugins-34e199d2                           34e199d2:latest

  [V] View plugins for a build
  [B] Back to main menu
  [Q] Quit

Select a build number, or V/B/Q:
```

- Option 1–5: proceed directly to Step 9 with that standard's image
- `[V]` → go to Step 3a-view (select a build to preview)
- `[B]` → return to Step 3
- `[Q]` → exit the skill immediately with no changes made

### 3a-view. View build plugins submenu

Show all standard builds for preview selection:

```
View Build Plugins
═════════════════════════════════════════

Select a build to preview its plugins:

  [1] base
  [2] coding
  [3] ext
  [4] all
  [5] base-ext-skills

  [B] Back to existing builds menu
  [Q] Quit

Select a build:
```

- Option 1–5: go to Step 3a-plugins (display plugin list for that build)
- `[B]` → return to Step 3a
- `[Q]` → exit the skill immediately with no changes made

### 3a-plugins. Display existing build plugins

After selecting a build (either directly from Step 3a or from Step 3a-view), display the full plugin list for that build. For plugins containing multiple sub-skills/components (fetched from marketplace metadata), list them indented under the parent plugin. Display total estimated size at the bottom:

```
Build: base (10 plugins) — Estimated size: ~8MB
════════════════════════════════════════════════════════════

     Plugin                 Size  Marketplace
  ────────────────────────────────────────────────────────────
  1  claude-code-setup     S     claude-plugins-official
  2  claude-md-management  S     claude-plugins-official
  3  explanatory-output-style S  claude-plugins-official
  4  hookify               M     claude-plugins-official
  5  learning-output-style S     claude-plugins-official
  6  math-olympiad         S     claude-plugins-official
  7  playground            M     claude-plugins-official
  8  ralph-loop            S     claude-plugins-official
  9  session-report        S     claude-plugins-official
  10 skill-creator         M     claude-plugins-official

Plugins with sub-components:
  (none in this build)

Size breakdown: 7×S (~3.5MB) + 3×M (~4.5MB) = ~8MB
S = <1MB   M = 1–10MB   L = >10MB

Use this build? [y/n]:
```

Example with plugins containing sub-components:

```
Build: base-ext-skills (26 plugins) — Estimated size: ~37MB
════════════════════════════════════════════════════════════

     Plugin                 Size  Marketplace
  ────────────────────────────────────────────────────────────
  1  claude-code-setup     S     claude-plugins-official
  ...
  11 document-skills       M     anthropic-agent-skills
     └─ pdf-extract
     └─ doc-convert
     └─ text-analysis
  ...

Plugins with sub-components:
  • document-skills: pdf-extract, doc-convert, text-analysis

Size breakdown: 12×S (~6MB) + 12×M (~18MB) + 2×L (~13MB) = ~37MB
S = <1MB   M = 1–10MB   L = >10MB

Use this build? [y/n]:
```

- `[y]` → proceed to Step 9 with that standard's image
- `[n]` → return to Step 3a-view (if accessed via [V]) or Step 3a (if selected directly from 1-5)
- `[q]` → exit the skill immediately with no changes made

### 3b. Custom build options submenu

Show options for building a custom plugin layer:

```
Build Custom Plugin Layer
═════════════════════════════════════════

Choose how to build your custom layer.

  [P] Pick from prebuilt lists (select multiple, add/remove plugins)
  [M] Manual marketplace selection (browse all plugins)
  [S] Search across all marketplaces
  [B] Back to main menu
  [Q] Quit

Select an option:
```

- `[P]` → continue to Step 3c (prebuilt lists selector)
- `[M]` → continue to Step 4 (marketplace menu with empty selections)
- `[S]` → go to Step 4-search (search for plugins across all marketplaces)
- `[B]` → return to Step 3
- `[Q]` → exit the skill immediately with no changes made

### 3c. Prebuilt lists selector

Load prebuilt lists from `plugin-lists.json` (all entries with `"type": "standard"` or `"type": "prebuilt-list"`). User can select **multiple** prebuilts, and selections are accumulated. After selections, option to proceed or browse marketplaces.

**Critical:** When prebuilts are selected, immediately populate the session selections map using the `distribution` data from `plugin-lists.json` for each selected prebuilt. This ensures marketplace-specific counts are always accurate.

```
Pick from Prebuilt Lists
═════════════════════════════════════════════════════

Select one or more prebuilt lists to combine them.
You can customize further in the marketplace menu.

  [1] base                    10 plugins (general-purpose)
  [2] coding                  32 plugins (base + software development)
  [3] ext                     25 plugins (base + external/third-party)
  [4] all                     47 plugins (base + coding + external)
  [5] base-ext-skills         26 plugins (base + ext + document-skills)
  [6] base-plus-general-skills 26 plugins (base + general skills, no LSPs)

  [V] View plugins in a prebuilt list
  [D] Done with prebuilts → go to marketplace menu
  [R] Ready to build — skip marketplace menu
  [B] Back to custom options
  [Q] Quit

Selected prebuilts (0): 

Select numbers to toggle, or V/D/R/B/Q:
```

- Number input: toggle those prebuilt selections on/off, immediately update selections map using plugin-lists.json distribution, update selection count, redisplay with live marketplace counts
- `[V]` → go to Step 3c-view (select a prebuilt to preview)
- `[D]` → proceed to Step 4 (marketplace menu) with current selections populated across all marketplaces per plugin-lists.json distribution. User can add/remove from any marketplace.
- `[R]` → skip the marketplace menu and proceed directly to Step 6 (conflict detection). Use this when satisfied with prebuilt selections and no marketplace customization needed.
- `[B]` → return to Step 3b
- `[Q]` → exit the skill immediately with no changes made

### 3c-view. View prebuilt plugins submenu

Load prebuilt lists from standards.json (all entries with `"type": "standard"` or `"type": "prebuilt-list"`). Show all available prebuilt lists for preview selection:

```
View Prebuilt Plugins
═════════════════════════════════════════

Select a prebuilt list to preview its plugins:

  [1] base recommended
  [2] code support
  [3] 3rd party
  [4] all from official

  [B] Back to prebuilt lists menu
  [Q] Quit

Select a prebuilt:
```

- Option 1–4: go to Step 3c-plugins (display plugin list for that prebuilt)
- `[B]` → return to Step 3c
- `[Q]` → exit the skill immediately with no changes made

### 3c-plugins. Display prebuilt plugins

After selecting a prebuilt (from Step 3c-view), display the full plugin list for that prebuilt. For plugins containing sub-skills/components, list them indented:

```
Prebuilt: base recommended (10 plugins)
════════════════════════════════════════════════════════════

     Plugin                 Size  Marketplace
  ────────────────────────────────────────────────────────────
  1  claude-code-setup     S     claude-plugins-official
  2  claude-md-management  S     claude-plugins-official
  3  explanatory-output-style S  claude-plugins-official
  4  hookify               M     claude-plugins-official
  ...

  S = <1MB   M = 1–10MB   L = >10MB

Use this prebuilt? [y/n]:
```

- `[y]` → select this prebuilt (add to selections counter) and return to Step 3c
- `[n]` → return to Step 3c-view
- `[q]` → exit the skill immediately with no changes made

### 4. Marketplace menu (loop)

Initialise a selections map: `{ marketplace_repo → Set<plugin_name> }` (all empty).

Display the marketplace menu. Show live selection counts next to each marketplace:

```
Custom Plugin Builder — Select Marketplaces
════════════════════════════════════════════

  [1] anthropics/claude-plugins-official    Anthropic       0 selected
  [2] anthropics/skills                     Anthropic       0 selected
  [3] anthropics/knowledge-work-plugins     Anthropic       0 selected
  [4] anthropics/financial-services-plugins Anthropic       0 selected
  [5] anthropics/claude-plugins-community   3rd Party ⚠️    0 selected

  [S] Search across all marketplaces
  [C] Clear ALL selections
  [D] Done — review selections
  [Q] Quit

Select a marketplace to browse, or S/C/D/Q:
```

- Selecting a marketplace number → go to Step 5 for that marketplace, then return here
- `[S]` → go to Step 4-search (search for plugins across all marketplaces)
- `[C]` → clear the entire selections map, redisplay menu
- `[D]` → go to Step 6
- `[Q]` → exit the skill immediately with no changes made

### 4-search. Global plugin search prompt

Display search prompt:

```
Search All Marketplaces
════════════════════════════════════════════════════════════════

Search for plugins by keyword across all available marketplaces
(searches plugin names and descriptions):

> 
```

- Accepts any search term (case-insensitive)
- Minimum 1 character, maximum 50 characters
- **Match rule (substring anywhere)**: the term can appear anywhere in the plugin name or description (case-insensitive substring match). Use `bash ./scripts/plugin-search.sh "$TERM" "."` which implements case-insensitive `contains()` matching via jq.
- Go to Step 4-search-results with matching plugins from all marketplaces
- Accepts empty input → return to Step 4 without searching

### 4-search-results. Global search results

Display all plugins matching the search keyword across all marketplaces. Number them sequentially. Mark selected plugins with `✓`. Show size category, source (Anthropic/3rd Party), and marketplace for each plugin:

```
Search Results — Global plugin search: "code"  — 31 results across all marketplaces
════════════════════════════════════════════════════════════════════════════════════════

     Plugin                 Marketplace                      Size  Source     Description
  ───────────────────────────────────────────────────────────────────────────────────────
  1  ✓ code-simplifier      claude-plugins-official          S     Anthropic  Reviews and simplifies changed code
  2    code-review          claude-plugins-official          M     Anthropic  Automated code review tool
  3    claude-code-setup    claude-plugins-official          S     Anthropic  Initial Claude Code setup guide
  4    code-analyzer        financial-services-plugins       M     Anthropic  Financial code analyzer
  5    coding-tools         knowledge-work-plugins           M     Anthropic  General coding utilities
  6    external-code-tool   claude-plugins-community         M     3rd Party  External code analysis plugin
  7  ...

  ✓ = currently selected    S = <1MB   M = 1–10MB   L = >10MB

Enter numbers to toggle (e.g. 1 3 5)
[A] Select all results   [C] Clear search results   [B] Back to marketplace menu   [Q] Quit:
```

- Number input → toggle those plugins, redisplay with updated `✓` markers
- `[A]` → select all plugins in this search result, redisplay with updated `✓` markers
- `[C]` → deselect all plugins from this search result (other selections unaffected)
- `[B]` → return to Step 4
- `[Q]` → exit the skill immediately with no changes made

After any selection change, redisplay the results with updated `✓` markers.

### 5. Plugin submenu (per marketplace)

**If the marketplace has >20 plugins**, first show a category picker (Step 5a), then the plugin list filtered to that category (Step 5b). Otherwise skip directly to Step 5b showing all plugins.

#### 5a. Category picker (large marketplaces only)

Group all plugins by their `category` field. Plugins with no `category` go in **Other**. Show selection counts across all categories so the user can see what they've already picked:

```
Marketplace: anthropics/claude-plugins-official  (Anthropic)  — 146 plugins
════════════════════════════════════════════════════════════════════════════════

  Browse by category:

  [1] development    61 plugins    0 selected
  [2] productivity   26 plugins    0 selected
  [3] database       11 plugins    0 selected
  [4] security        5 plugins    0 selected
  [5] deployment      5 plugins    0 selected
  [6] monitoring      4 plugins    0 selected
  [7] design          2 plugins    0 selected
  [8] learning        2 plugins    0 selected
  [9] Other          30 plugins    0 selected

  [A] Select ALL plugins in this marketplace
  [C] Clear ALL selections in this marketplace
  [S] Search for plugins by keyword
  [B] Back to marketplace menu
  [Q] Quit

Select a category, A/C/S/B/Q:
```

- Category number → go to Step 5b for that category, then return here with updated counts
- `[A]` → select every plugin in this marketplace, redisplay with updated counts
- `[C]` → clear all selections for this marketplace, redisplay
- `[S]` → go to Step 5a-search (enter keyword to search plugins across all categories)
- `[B]` → return to Step 4
- `[Q]` → exit the skill immediately with no changes made

#### 5a-search. Plugin search prompt

Display search prompt:

```
Marketplace: anthropics/claude-plugins-official  (Anthropic)
════════════════════════════════════════════════════════════════

Search for plugins by keyword (searches plugin names and descriptions):

> 
```

- Accepts any search term (case-insensitive)
- Minimum 1 character, maximum 50 characters
- **Match rule (substring anywhere)**: the term can appear anywhere in the plugin name or description (case-insensitive substring match). Same as Step 4-search.
- Go to Step 5a-search-results with matching plugins
- Accepts empty input → return to Step 5a without searching

#### 5a-search-results. Search results

Display all plugins matching the search keyword across all categories. Number them sequentially. Mark selected plugins with `✓`. Show size category, category, and source (Anthropic/3rd Party) for each plugin:

```
Marketplace: anthropics/claude-plugins-official  (Anthropic)  › search: "code"  — 24 results
════════════════════════════════════════════════════════════════════════════════════════════

     Plugin                 Category      Size  Source     Description
  ────────────────────────────────────────────────────────────────────────────
  1  ✓ code-simplifier      development   S     Anthropic  Reviews and simplifies changed code
  2    code-review          development   M     Anthropic  Automated code review tool
  3    claude-code-setup    development   S     Anthropic  Initial Claude Code setup guide
  4    external-code-tool   development   M     3rd Party  External code analysis plugin
  5  ...

  ✓ = currently selected    S = <1MB   M = 1–10MB   L = >10MB

Enter numbers to toggle (e.g. 1 3 5)
[A] Select all results   [C] Clear search results   [B] Back to category picker   [Q] Quit:
```

- Number input → toggle those plugins, redisplay with updated `✓` markers
- `[A]` → select all plugins in this search result, redisplay with updated `✓` markers
- `[C]` → deselect all plugins from this search result (other selections unaffected)
- `[B]` → return to Step 5a
- `[Q]` → exit the skill immediately with no changes made

After any selection change, redisplay the results with updated `✓` markers.

#### 5b. Plugin list (filtered or full)

Display plugins for the current category (or all plugins for small marketplaces). Number them sequentially. Mark selected plugins with `✓`. Show size category for each plugin:

```
Marketplace: anthropics/claude-plugins-official  (Anthropic)  › development  — 61 plugins
════════════════════════════════════════════════════════════════════════════════════════════

     Plugin                 Size  Description
  ────────────────────────────────────────────────────────────────────────────
  1  hookify                M     Behavioral automation rules
  2  pr-review-toolkit      M     PR review with specialized agents
  3  code-simplifier        S     Reviews and simplifies changed code
  4  ...

  ✓ = currently selected    S = <1MB   M = 1–10MB   L = >10MB

Enter numbers to toggle (e.g. 1 3 5)
[A] Select all in this category   [C] Clear this category   [B] Back   [Q] Quit:
```

- Number input → toggle those plugins, redisplay with updated `✓` markers
- `[A]` → select all plugins in this category/view
- `[C]` → deselect all plugins in this category/view (other categories unaffected)
- `[B]` → return to Step 5a (if category picker was shown) or Step 4 (if flat list)
- `[Q]` → exit the skill immediately with no changes made

After any selection change, redisplay the table with updated `✓` markers.

### 6. Conflict detection

Before proceeding to review, scan for duplicate plugin names across all selected marketplaces.

If any plugin name appears in more than one selected marketplace, warn:

```
⚠️  Duplicate plugin names detected:

  "frontend-design" selected from both:
    • anthropics/claude-plugins-official
    • anthropics/skills

  Keeping only one copy per plugin name. Which source should take precedence?
  [1] anthropics/claude-plugins-official
  [2] anthropics/skills
```

Resolve each conflict before proceeding. Remove the non-chosen duplicate from selections.

### 7. Review and confirm

**Redundancy detection:** Before displaying selections, scan for plugins that are sub-components of other selected plugins in the same marketplace. If found, remove the redundant sub-components and display a notice. Then display all remaining selected plugins grouped by marketplace with their size categories. Calculate total estimated size. If nothing selected, say so:

**Example with redundancy detected:**

```
⚠️  Removed redundant plugins:

  "pdf" was already included in "document-skills"
  → Removed: pdf

Review Selections
═════════════════════════════════════════════════════

  anthropics/claude-plugins-official (Anthropic) — 3 plugins  (~6MB)
    • hookify                 (M)
    • pr-review-toolkit       (M)
    • code-simplifier         (S)

  anthropics/skills (Anthropic) — 1 plugin  (~12MB)
    • document-skills         (M)

  ─────────────────────────────────────────────────
  Total: 4 plugins across 2 marketplaces
  Estimated layer size: ~18MB

Proceed? [y/n/q]:
```

**Example with no redundancy:**

```
Review Selections
═════════════════════════════════════════════════════

  anthropics/claude-plugins-official (Anthropic) — 3 plugins  (~6MB)
    • hookify                 (M)
    • pr-review-toolkit       (M)
    • code-simplifier         (S)

  anthropics/skills (Anthropic) — 2 plugins  (~3MB)
    • pdf                     (M)
    • pptx                    (M)

  ─────────────────────────────────────────────────
  Total: 5 plugins across 2 marketplaces
  Estimated layer size: ~9MB

  [ No plugins selected. Image will be an empty layer. ]

Proceed? [y/n/q]:
```

Size legend: S = <1MB, M = 1–10MB, L = >10MB

- `[n]` → return to Step 4
- `[y]` → continue to Step 7a
- `[q]` → exit the skill immediately with no changes made

### 7a. Check against prebuilt lists

Compare the custom selection against the four predefined prebuilt lists to see if there's a match.

**Before offering an existing build, verify the repo actually exists:**
```bash
gh api repos/sun2admin/REPO_NAME 2>/dev/null
```

If the repo does NOT exist, skip to Step 8 (create the repo).

**If exact match found AND repo exists:**

```
✓ Your selection matches an existing build

  Prebuilt list: "base recommended" (10 plugins)
  Existing build: "base"
  Image: ghcr.io/sun2admin/claude-anthropic-base-plugins-container:latest

  This build is already available. Using the existing image instead of
  creating a new one.

Continue? [c/q]:
```

- `[c]` → go to Step 9 with the existing build's image
- `[q]` → exit the skill immediately with no changes made

**If no match found:**

```
No matching prebuilt list found for your custom selection.

Would you like to save this as a new prebuilt list for future use?
(The plugins will be saved to standards.json and appear in Step 3c on next run)

Save as prebuilt? [y/n]:
```

- `[y]` → prompt for prebuilt name, prompt for description, save to standards.json, then continue to Step 8
- `[n]` → continue directly to Step 8

When `[y]` is selected, prompt:

```
Name this prebuilt list (max 30 chars, alphanumeric + hyphens):
> 
```

After name is accepted, prompt for description:

```
Describe this prebuilt list (optional, max 80 chars):
> 
```

Then save entry to standards.json with the following structure and continue to Step 8:

```json
{
  "name": "PREBUILT_NAME",
  "description": "DESCRIPTION (or auto-generated if skipped)",
  "type": "prebuilt-list",
  "plugins": [
    { "marketplace": "anthropics/claude-plugins-official", "plugin": "hookify" },
    ...
  ]
}
```

The new prebuilt will appear in Step 3c (Prebuilt Lists) on all subsequent runs.

### 7b. Redundancy detection algorithm (implementation)

Before displaying Step 7 (Review and confirm), perform the following redundancy check:

**Input**: `selections` map: `{ marketplace_repo → Set<plugin_name> }`

**Algorithm**:

1. For each marketplace in selections:
   a. Get the list of plugin metadata for that marketplace from the cached plugin data (fetched in Step 2)
   b. For each selected plugin name in this marketplace:
      - Check if this plugin has a `skills` array in its metadata
   c. Create a set of all sub-component names: `sub_components = union of all skills arrays across all selected plugins`
   d. For each selected plugin name:
      - If this plugin name appears in `sub_components`, mark it for removal
   e. Remove all marked sub-component plugins from the selections for this marketplace

2. Build a removal notice if any plugins were removed:
   ```
   ⚠️  Removed redundant plugins:
   
     "<removed_plugin>" was already included in "<parent_plugin>"
     → Removed: <removed_plugin>
   
     [repeat for each removed plugin]
   ```

3. Display the removal notice (if any), then continue with the cleaned selections for Step 7 display.

**Example**: If a user selects both `document-skills` and `pdf` from the same marketplace, and `document-skills` has `skills: ["pdf-extract", "doc-convert", "text-analysis"]`, the `pdf` plugin may be a direct match or a sub-skill that should not be selected alongside its parent. The algorithm checks for exact name matches in the parent's `skills` array and removes them.

### 8. Hash check and deduplication

Compute the canonical plugin set fingerprint:
1. Build a sorted list of `"marketplace_repo/plugin_name"` strings from all selections
2. Serialise as newline-joined sorted list
3. Compute SHA-256, take first 8 hex characters → `HASH`
4. Repo name: `claude-plugins-HASH`

Check if this exact repo already exists:
```bash
gh api repos/sun2admin/claude-plugins-HASH 2>/dev/null
```

**If repo exists:**
```
✓ A plugin image with your exact selections already exists:
  sun2admin/claude-plugins-HASH

  Image: ghcr.io/sun2admin/claude-plugins-HASH:latest

Use this existing image? [y/n/q]:
```
- `[y]` → go to Step 9 with that image
- `[n]` → return to Step 4
- `[q]` → exit the skill immediately with no changes made

**If repo does not exist:** continue to Step 8a.

### 8a. Prompt for human name and description

```
Name this build (used to identify it in future runs):
> 
```

- Name must be non-empty, no spaces (hyphens OK)
- Check `standards.json` — if name already exists, warn and prompt again

After name is accepted, prompt for description:

```
Describe this build (optional, max 80 chars):
> 
```

- Description is optional (user can press Enter to skip)
- If provided, must be non-empty after trimming whitespace
- If empty or skipped, auto-generate default: `"Custom build — HASH"`

### 8b. Create the repo and push files

```bash
gh repo create sun2admin/claude-plugins-HASH \
  --private \
  --description "Claude Code plugin layer — HUMAN_NAME (DESCRIPTION)" \
  --clone=false
```

Use DESCRIPTION if provided by user, or auto-generated default "Custom build — HASH" if skipped.

Set topic:
```bash
gh api repos/sun2admin/claude-plugins-HASH/topics \
  --method PUT \
  --field names[]="anthropic-plugins"
```

Generate and push four files in a single commit via GitHub API (`mcp__github__push_files`):

**`Dockerfile`** — group installs by marketplace, re-add marketplace before each group:

```dockerfile
ARG BASE_IMAGE=ghcr.io/sun2admin/ai-install-layer:claude
FROM ${BASE_IMAGE}

USER root
RUN mkdir -p /opt/claude-custom-plugins && chown claude:claude /opt/claude-custom-plugins

USER claude
ENV CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-custom-plugins

# <marketplace_repo> (<marketplace_name>)
RUN claude plugin marketplace add <marketplace_repo> && \
    claude plugin install <plugin1>@<marketplace_name> && \
    claude plugin install <plugin2>@<marketplace_name>

# repeat block per marketplace

ENV CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-custom-plugins
```

Note: for `anthropics/claude-plugins-official` the install suffix (`@claude-plugins-official`) may be omitted if it is the default marketplace — verify at runtime from the marketplace.json `name` field.

**`plugin-manifest.json`**:
```json
{
  "hash": "HASH",
  "human_name": "HUMAN_NAME",
  "description": "DESCRIPTION",
  "created_at": "YYYY-MM-DD",
  "plugins": [
    { "marketplace": "anthropics/claude-plugins-official", "marketplace_name": "claude-plugins-official", "plugin": "hookify" },
    { "marketplace": "anthropics/skills", "marketplace_name": "anthropic-agent-skills", "plugin": "pdf" }
  ]
}
```

**`.github/workflows/build-image.yml`**:
```yaml
name: Build and Push Image

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    env:
      FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
    strategy:
      matrix:
        include:
          - tag: latest
            base: ghcr.io/sun2admin/ai-install-layer:claude
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v4
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/sun2admin/claude-plugins-HASH:${{ matrix.tag }}
          build-args: |
            BASE_IMAGE=${{ matrix.base }}
```

**`README.md`**:
```markdown
# claude-plugins-HASH (HUMAN_NAME)

Custom Claude Code plugin layer image built by the `new-plugin-layer` skill.

## Plugins

| Marketplace | Plugin |
|---|---|
| anthropics/... | plugin-name |

## Usage

Reference in `devcontainer.json`:
\`\`\`json
"image": "ghcr.io/sun2admin/claude-plugins-HASH:latest"
\`\`\`
```

### 8c. Manual package access step

Display:

```
⚠️  Manual step required before the build will succeed
════════════════════════════════════════════════════════

The new repo needs read access to the ai-install-layer package.

1. Go to: https://github.com/users/sun2admin/packages/container/package/ai-install-layer
2. Click "Package settings"
3. Scroll to "Manage Actions access"
4. Click "Add repository"
5. Search for and select: sun2admin/claude-plugins-HASH
6. Set role to: Read
```

Do NOT prompt for input or wait for user confirmation in the message. The user will grant access manually and proceed when ready.

### 8d. Trigger build and save

```bash
gh workflow run build-image.yml --repo sun2admin/claude-plugins-HASH
```

Update `standards.json` — append new entry:
```json
{
  "name": "HUMAN_NAME",
  "description": "DESCRIPTION",
  "repo": "claude-plugins-HASH",
  "image": "ghcr.io/sun2admin/claude-plugins-HASH"
}
```

Use user-provided DESCRIPTION if provided, or auto-generated default "Custom build — HASH" if user skipped.

Commit and push `standards.json` to the `build-with-claude` repo:
```bash
git -C /workspace/claude add standards.json
git -C /workspace/claude commit -m "Add custom plugin build: HUMAN_NAME (HASH)"
git -C /workspace/claude push
```

### 9. Output image reference

Display the final result:

```
════════════════════════════════════════════
Plugin layer ready:

Available image tag:
  • ghcr.io/sun2admin/<repo>:latest

Use in devcontainer.json:
  "image": "ghcr.io/sun2admin/<repo>:latest"

Note: if a new build was triggered, allow ~20-30 min for
GitHub Actions to complete before rebuilding your devcontainer.
════════════════════════════════════════════
```

All plugins selected are baked into the `:latest` tag image, built on top of ai-install-layer:claude.

## Existing Build Plugin Contents

Reference for Step 3a-plugins plugin list display:

### Build 1: base (10 plugins from claude-plugins-official)
- claude-code-setup (S)
- claude-md-management (S)
- explanatory-output-style (S)
- hookify (M)
- learning-output-style (S)
- math-olympiad (S)
- playground (M)
- ralph-loop (S)
- session-report (S)
- skill-creator (M)

### Build 2: coding (32 plugins = 10 base + 22 additional from claude-plugins-official)
**Base (10):** claude-code-setup, claude-md-management, explanatory-output-style, hookify, learning-output-style, math-olympiad, playground, ralph-loop, session-report, skill-creator

**Code flow (6):** code-review (M), code-simplifier (S), commit-commands (M), feature-dev (M), pr-review-toolkit (M), security-guidance (M)

**Dev tooling (4):** agent-sdk-dev (M), frontend-design (M), mcp-server-dev (M), plugin-dev (M)

**LSP servers (12):** clangd-lsp (L), csharp-lsp (L), gopls-lsp (L), jdtls-lsp (L), kotlin-lsp (L), lua-lsp (L), php-lsp (L), pyright-lsp (L), ruby-lsp (L), rust-analyzer-lsp (L), swift-lsp (L), typescript-lsp (L)

### Build 3: ext (25 plugins = 10 base + 15 from claude-plugins-community)
**Base (10):** claude-code-setup, claude-md-management, explanatory-output-style, hookify, learning-output-style, math-olympiad, playground, ralph-loop, session-report, skill-creator

**External (15):** asana (M), context7 (M), discord (M), fakechat (S), firebase (M), github (L), gitlab (M), greptile (M), imessage (S), laravel-boost (M), linear (M), playwright (L), serena (M), telegram (M), terraform (M)

### Build 4: all (47 plugins = 10 base + 22 coding + 15 external)
Combination of base, coding, and ext builds.

### Build 5: base-ext-skills (26 plugins = 10 base + 15 external + 1 from skills)
**Base (10):** claude-code-setup, claude-md-management, explanatory-output-style, hookify, learning-output-style, math-olympiad, playground, ralph-loop, session-report, skill-creator

**Skills (1):** document-skills (M)

**External (15):** asana (M), context7 (M), discord (M), fakechat (S), firebase (M), github (L), gitlab (M), greptile (M), imessage (S), laravel-boost (M), linear (M), playwright (L), serena (M), telegram (M), terraform (M)

## Prebuilt Plugin Lists

The four prebuilt options (Step 3c) are derived from the official container repos. These can be customized after selection by adding/removing plugins from any marketplace.

### Base Recommended (10 plugins)
From `claude-anthropic-base-plugins-container`:
- claude-code-setup, claude-md-management, explanatory-output-style, hookify, learning-output-style, math-olympiad, playground, ralph-loop, session-report, skill-creator

### Code Support (22 plugins)
From `claude-anthropic-coding-plugins-container` (in addition to base):

**Code flow (6):** code-review, code-simplifier, commit-commands, feature-dev, pr-review-toolkit, security-guidance

**Dev tooling (4):** agent-sdk-dev, frontend-design, mcp-server-dev, plugin-dev

**LSP servers (12):** clangd-lsp, csharp-lsp, gopls-lsp, jdtls-lsp, kotlin-lsp, lua-lsp, php-lsp, pyright-lsp, ruby-lsp, rust-analyzer-lsp, swift-lsp, typescript-lsp

### 3rd Party (15 plugins)
From `claude-anthropic-ext-plugins-container` (in addition to base):
- asana, context7, discord, fakechat, firebase, github, gitlab, greptile, imessage, laravel-boost, linear, playwright, serena, telegram, terraform

### All Official (47 plugins)
Base + Code + 3rd Party combined.

## standards.json Structure

The file stores all named builds and prebuilt lists with the following schema:

```json
{
  "standards": [
    {
      "name": "base",
      "description": "General-purpose plugins",
      "type": "standard",
      "repo": "claude-anthropic-base-plugins-container",
      "image": "ghcr.io/sun2admin/claude-anthropic-base-plugins-container"
    },
    {
      "name": "base-plus-general-skills",
      "description": "Base + general skills (no coding LSPs)",
      "type": "prebuilt-list",
      "repo": "claude-plugins-3f889e47",
      "image": "ghcr.io/sun2admin/claude-plugins-3f889e47"
    }
  ],
  "plugins": {
    "anthropics/claude-plugins-official": {
      "hookify": {"size_kb": 250, "category": "S"},
      ...
    }
  }
}
```

**Entry types:**
- `"standard"` — One of the 4 core prebuilt collections (base, coding, ext, all)
- `"prebuilt-list"` — A saved collection created by the user in Step 7a (appears in Step 3c on all subsequent runs)
- `"custom-build"` — A one-off custom build created for a specific use case (appears in Step 3a)

**Persistence:** All entries persist across scenarios:
1. **First run** — Loaded from repo on initial clone
2. **Subsequent restarts** — Loaded from workspace (unchanged since first run or last save)
3. **Reconnects** — Loaded from workspace (all prior saves intact)

Saved prebuilt lists remain available indefinitely across all three scenarios.

## Plugin Size Caching

Size metadata is cached in `standards.json` under a `plugins` field to avoid redundant GitHub API calls. On subsequent runs, the skill reads cached sizes instead of fetching. If a plugin is not cached, its size is fetched fresh and added to the cache. `standards.json` is updated after each build.

Size categories: **S** ≤1MB, **M** 1–10MB, **L** >10MB.

## Notes

- This skill is only available in `build-with-claude` — it manages infrastructure, not project code
- Plugin images always build both `:latest` and `:playwright` tags via matrix
- All created repos are private with the `anthropic-plugins` GitHub topic
- Hash is computed from the canonical sorted plugin set — identical selections always produce the same repo, preventing duplicates
- `standards.json` is the source of truth for named builds; custom builds added here are available on all subsequent runs
- Size estimates are based on GitHub repo size and are approximate; actual layer sizes depend on compression and shared dependencies
