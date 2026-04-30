# layer2-ai-install

AI tool installation layer for the layered container architecture.

**Base**: `ghcr.io/sun2admin/layer1-ai-depends:latest`

**Variants**:
- `:claude` — Installs Claude Code CLI, creates `claude` user
- `:gemini` — Installs Gemini CLI, creates `gemini` user

## Architecture

Layer 2 of the 4-layer stack:
1. layer1-ai-depends (system packages)
2. **layer2-ai-install** (AI tool + user setup)
3. claude-plugins-* (pre-baked plugins)
4. Project repos (reference plugins image)

## Building

Both variants build automatically via GitHub Actions matrix when changes are pushed to main.

### Manual build:
```bash
# Claude variant
docker build --build-arg AI_TYPE=claude --build-arg AI_PACKAGE=@anthropic-ai/claude-code -t layer2-ai-install:claude .

# Gemini variant
docker build --build-arg AI_TYPE=gemini --build-arg AI_PACKAGE=@google/gemini-cli -t layer2-ai-install:gemini .
```

## Usage

In devcontainer.json:
```json
{
  "image": "ghcr.io/sun2admin/layer2-ai-install:claude"
}
```

Or for Gemini:
```json
{
  "image": "ghcr.io/sun2admin/layer2-ai-install:gemini"
}
```
