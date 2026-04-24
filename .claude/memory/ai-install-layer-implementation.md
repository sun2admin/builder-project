---
name: ai-install-layer Implementation (Layer 2)
description: Conditional Dockerfile with :claude and :gemini variants; image-based replacement for deprecated claude-install-container
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## ai-install-layer Repo

**Repository**: `https://github.com/sun2admin/ai-install-layer`

**Purpose**: Layer 2 of 4-layer stack. Installs AI tool (Claude Code or Gemini CLI) and creates corresponding user with environment setup.

**Replaces**: Deprecated claude-install-container (features approach, deleted 2026-04-24)

---

## Architecture: Conditional Dockerfile

**Single Dockerfile with conditional logic via ARGs:**

```dockerfile
ARG BASE_IMAGE=ghcr.io/sun2admin/base-ai-layer:latest
FROM ${BASE_IMAGE}

# Layer 1: Conditionally install AI tool
ARG AI_TYPE=claude
ARG AI_PACKAGE=@anthropic-ai/claude-code

RUN if [ "$AI_TYPE" = "gemini" ]; then \
    AI_PACKAGE="@google/gemini-cli"; \
fi && \
npm install -g ${AI_PACKAGE} && \
npm cache clean --force

# Layer 2: Create user (username = AI_TYPE)
ARG USERNAME=${AI_TYPE}

RUN useradd -m -s /bin/bash ${USERNAME} && \
    mkdir -p /commandhistory && \
    chown -R ${USERNAME} /commandhistory && \
    mkdir -p /home/${USERNAME}/.claude /home/${USERNAME}/.ssh && \
    chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude ... (etc.)

USER ${USERNAME}
```

**Key design:**
- `USERNAME` variable matches `AI_TYPE` (claude user for :claude, gemini user for :gemini)
- Conditional `AI_PACKAGE` selection (Claude Code vs Gemini CLI)
- All user setup is identical; only names/packages differ
- No features, no install.sh scripts—all baked into image

---

## Tag Variants

### :claude
- **AI_TYPE**: claude
- **AI_PACKAGE**: @anthropic-ai/claude-code
- **USERNAME**: claude
- **Base**: ghcr.io/sun2admin/base-ai-layer:latest
- **Use**: Default Claude Code projects

### :gemini
- **AI_TYPE**: gemini
- **AI_PACKAGE**: @google/gemini-cli
- **USERNAME**: gemini
- **Base**: ghcr.io/sun2admin/base-ai-layer:latest
- **Use**: Gemini-based projects (e.g., career-ops Phase 2)

---

## GitHub Actions Matrix Build

**File**: `.github/workflows/build-and-push.yml`

Matrix strategy with two jobs:
1. `:claude` variant
   - AI_TYPE=claude
   - AI_PACKAGE=@anthropic-ai/claude-code
   - Tag: `ghcr.io/sun2admin/ai-install-layer:claude`

2. `:gemini` variant
   - AI_TYPE=gemini
   - AI_PACKAGE=@google/gemini-cli
   - Tag: `ghcr.io/sun2admin/ai-install-layer:gemini`

Both build in parallel; cache via GitHub Actions.

---

## Usage in devcontainer.json

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

No features needed; everything is in the image.

---

## Status & Next Steps

### Completed ✅
1. ✅ Both :claude and :gemini variants building successfully
2. ✅ All 8 downstream plugin layer repos updated to use ai-install-layer:claude base
3. ✅ All plugin repos building successfully with new base
4. ✅ Complete 4-layer architecture validated end-to-end

### Future (when ready)
- Create gemini-plugins-* variants using :gemini base for Phase 2 expansion

---

## Current Status (2026-04-23, COMPLETE)

✅ **ai-install-layer**: Both :claude and :gemini variants published and working
✅ **Plugin migration**: All 8 plugin repos successfully migrated to use ai-install-layer:claude
✅ **4-layer stack**: Complete architecture operational (Layer 1 → 2 → 3 → 4)
