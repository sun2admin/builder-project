---
name: Playwright Chromium/Firefox/WebKit in Dev Containers
description: How to bake Playwright browser binaries into devcontainer images using multi-stage builds; current implementation in layer1-ai-depends
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## Current Approach: layer1-ai-depends

**See**: `layer1-ai-depends` repo for the current production implementation.

Browser binaries (Chromium, Firefox, WebKit) are large (~300-500MB each) and require system deps to download. Use a dedicated `playwright-builder` stage that conditionally installs browsers based on ARG.

### playwright-builder Stage

```dockerfile
FROM node:22 AS playwright-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists*

RUN python3 -m pip install --no-cache-dir --break-system-packages playwright

ARG BROWSERS=chromium
RUN mkdir -p /root/.cache/ms-playwright && \
    for browser in $BROWSERS; do \
    python3 -m playwright install "$browser"; \
done
```

**Key points:**
- `--break-system-packages` flag (safe in ephemeral build context)
- `mkdir -p /root/.cache/ms-playwright` ensures directory exists even if `$BROWSERS` is empty (:light variant)
- Supports multiple browsers: `chromium`, `firefox`, `webkit` (space-separated)

### Final Stage (Conditionally Copy Playwright)

```dockerfile
FROM base AS final

ARG INCLUDE_PLAYWRIGHT=false
COPY --from=playwright-builder /root/.cache/ms-playwright /tmp/playwright-cache

RUN if [ "$INCLUDE_PLAYWRIGHT" = "true" ]; then \
    mkdir -p /home/node/.cache/ms-playwright && \
    cp -r /tmp/playwright-cache/* /home/node/.cache/ms-playwright/ && \
    /opt/venv/bin/pip install --no-cache-dir playwright && \
    for browser in $BROWSERS; do \
    /opt/venv/bin/playwright install-deps "$browser"; \
    done; \
fi

ENV PLAYWRIGHT_BROWSERS_PATH=/home/node/.cache/ms-playwright
```

## Tag Variants (layer1-ai-depends)

| Tag | BROWSERS | Status |
|-----|----------|--------|
| `:light` | (empty) | ✅ |
| `:latest` | (empty) | ✅ |
| `:playwright_with_chromium` | chromium | ✅ |
| `:playwright_with_firefox` | firefox | ✅ |
| `:playwright_with_safari` | webkit | ✅ |
| `:playwright_with_all` | chromium firefox webkit | ❌ exceeds runner time limit |

## If Using layer1-ai-depends Images

Reference the appropriate tag in your devcontainer:
```json
{
  "image": "ghcr.io/sun2admin/layer1-ai-depends:playwright_with_chromium"
}
```

No need to implement playwright-builder yourself — it's pre-baked.
