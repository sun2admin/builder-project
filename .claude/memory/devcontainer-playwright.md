---
name: Playwright Chromium/Firefox/WebKit in Dev Containers
description: How to bake Playwright browser binaries into devcontainer images using multi-stage builds; current implementation in base-ai-layer
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## Current Approach: base-ai-layer

**See**: `base-ai-layer` repo for the current production implementation.

Browser binaries (Chromium, Firefox, WebKit) are large (~300-500MB each) and require system deps to download. Use a dedicated `playwright-builder` stage that conditionally installs browsers based on ARG.

### playwright-builder Stage

```dockerfile
FROM node:20 AS playwright-builder

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
- Uses `--break-system-packages` flag (safe in ephemeral build context)
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

## Tag Variants (base-ai-layer)

| Tag | BROWSERS | Use Case |
|-----|----------|----------|
| `:light` | (empty) | Minimal, no Playwright |
| `:latest` | (empty) | Dev tools, no Playwright |
| `:playwright_with_chromium` | chromium | Chromium only |
| `:playwright_with_firefox` | firefox | Firefox only |
| `:playwright_with_safari` | webkit | WebKit (Safari) only |
| `:playwright_with_all` | chromium firefox webkit | All three browsers |

## Why This Approach

1. **Single Dockerfile**: Conditional builds via ARGs instead of separate repos
2. **Efficient layering**: :light and :latest avoid browser bloat; playwright variants are opt-in
3. **GitHub Actions matrix**: All variants build in parallel via CI/CD
4. **Minimal overhead for :light**: No Playwright installed or cached

## If Using base-ai-layer Images

Just reference the appropriate tag in your devcontainer:
```json
{
  "image": "ghcr.io/sun2admin/base-ai-layer:playwright_with_chromium"
}
```

No need to implement playwright-builder yourself — it's pre-baked.

## Historical Notes

Earlier approach used a venv in the playwright-builder stage. Current approach uses system-wide pip with `--break-system-packages` (safe in Docker) to simplify the build and avoid venv path complexity in final stages.
