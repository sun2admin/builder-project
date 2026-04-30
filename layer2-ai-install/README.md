# ai-install-layer

AI tool installation layer for the layered container architecture.

**Base**: `ghcr.io/sun2admin/base-ai-layer:latest`

**Variants**:
- `:claude` — Installs Claude Code CLI, creates `claude` user
- `:gemini` — Installs Gemini CLI, creates `gemini` user

## Architecture

Layer 2 of the 4-layer stack:
1. base-ai-layer (system packages)
2. **ai-install-layer** (AI tool + user setup)
3. ai-plugins-* (pre-baked plugins)
4. Project repos (use plugins image)

## Building

Both variants build automatically via GitHub Actions matrix when changes are pushed to main.

### Manual build:
```bash
# Claude variant
docker build --build-arg AI_TYPE=claude --build-arg AI_PACKAGE=@anthropic-ai/claude-code -t ai-install-layer:claude .

# Gemini variant
docker build --build-arg AI_TYPE=gemini --build-arg AI_PACKAGE=@google/gemini-cli -t ai-install-layer:gemini .
```

## Usage

In devcontainer.json:
```json
{
  "image": "ghcr.io/sun2admin/ai-install-layer:claude"
}
```

Or for Gemini:
```json
{
  "image": "ghcr.io/sun2admin/ai-install-layer:gemini"
}
```
