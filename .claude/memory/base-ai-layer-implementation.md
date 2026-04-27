---
name: base-ai-layer Implementation Details
description: Single Dockerfile with conditional builds for 6 tag variants; multi-stage playwright-builder; GitHub Actions matrix
type: project
originSessionId: 5521fc77-7f4d-4824-aa67-ff980c2a58df
---
## base-ai-layer Repo

**Repository**: `https://github.com/sun2admin/base-ai-layer`

**Purpose**: Replacement for deprecated `claude-depends-container` (deleted 2026-04-24). Uses conditional Dockerfile builds and tag variants instead of separate image repos.

---

## Dockerfile Structure

**Single Dockerfile with three conditional sections:**

### Stage 1: playwright-builder (always runs)
```dockerfile
FROM node:20 AS playwright-builder
RUN apt-get install python3-pip
RUN python3 -m pip install --no-cache-dir --break-system-packages playwright
RUN mkdir -p /root/.cache/ms-playwright && \
 for browser in $BROWSERS; do \
 python3 -m playwright install "$browser"; \
done
```

**Important**: 
- Uses `--break-system-packages` flag (safe in ephemeral build container)
- Directory is created even if BROWSERS is empty (:light variant)
- Cache artifacts are copied to final stage for playwright_with_* variants

### Base Stage: Always installs :light
```dockerfile
FROM node:20-slim AS base
RUN apt-get install -y --no-install-recommends \
 wget curl less git procps sudo fzf man-db unzip gnupg2 gh \
 iptables ipset iproute2 dnsutils aggregate \
 jq nano vim passwd openssh-client
```

These are Anthropic-recommended minimal packages (git, gh, jq, fzf, etc.).

### Layer 2: Conditionally installs :latest extras
```dockerfile
ARG INCLUDE_EXTRAS=false
RUN if [ "$INCLUDE_EXTRAS" = "true" ]; then \
 apt-get install -y --no-install-recommends \
 ripgrep fd-find tree bat shellcheck sqlite3 htop \
 python3 python3-pip python3-venv \
 poppler-utils pandoc \
 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
 libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-liberation && \
 python3 -m venv /opt/venv && \
 /opt/venv/bin/pip install --no-cache-dir \
 jupyterlab ipykernel pdfplumber pymupdf pypdf \
 reportlab weasyprint pandas numpy; \
fi
```

Creates venv at /opt/venv for isolation.

### Layer 3: Conditionally copies Playwright
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
```

Installs Playwright only for playwright_with_* variants.

---

## Build Arguments

| Variant | INCLUDE_EXTRAS | INCLUDE_PLAYWRIGHT | BROWSERS |
|---------|---|---|---|
| :light | false | false | (empty) |
| :latest | true | false | (empty) |
| :playwright_with_chromium | true | true | chromium |
| :playwright_with_firefox | true | true | firefox |
| :playwright_with_safari | true | true | webkit |
| :playwright_with_all | true | true | chromium firefox webkit |

---

## GitHub Actions Matrix Build

**File**: `.github/workflows/build-and-push.yml`

Defines 6 jobs in matrix strategy, one per variant. Each job:
1. Checks out code
2. Sets up Docker Buildx
3. Logs into GHCR
4. Runs `docker/build-push-action@v5` with variant-specific args
5. Prints build summary

**Tags format**:
```
ghcr.io/sun2admin/base-ai-layer:light
ghcr.io/sun2admin/base-ai-layer:latest
ghcr.io/sun2admin/base-ai-layer:playwright_with_chromium
(etc.)
```

**Caching**: Uses GitHub Actions cache (`type=gha`) to speed up rebuilds.

---

## Key Implementation Decisions

1. **Single Dockerfile, not six**: Cleaner maintenance, one source of truth
2. **Conditional RUN instead of stages**: Simpler for layers 2-3; only playwright-builder is a separate stage
3. **mkdir -p in playwright-builder**: Ensures cache directory always exists, preventing COPY failures for :light
4. **--break-system-packages in pip**: Safe in ephemeral build context; only needed for playwright-builder base (node:20)
5. **Tag variants at build time, not runtime**: Set via GitHub Actions matrix, not docker build --tag loops

---

## Testing

All 6 variants built successfully on 2026-04-23:
- ✅ :light (minimal, fast build)
- ✅ :latest (full extras)
- ✅ :playwright_with_chromium (500MB+ for Chromium)
- ✅ :playwright_with_firefox (500MB+ for Firefox)
- ✅ :playwright_with_safari (500MB+ for WebKit)
- ✅ :playwright_with_all (1.2GB+ for all three browsers)

Images are private on GHCR. Verified all pushed successfully to `ghcr.io/sun2admin/base-ai-layer`.

---

## Downstream Usage (Completed)

**ai-install-layer** (Layer 2) Dockerfile:
```dockerfile
FROM ghcr.io/sun2admin/base-ai-layer:latest
```

**All 8 plugin layer Dockerfiles** (Layer 3):
```dockerfile
FROM ghcr.io/sun2admin/ai-install-layer:claude
```

This cascades base-ai-layer updates automatically through all layers:
- base-ai-layer → ai-install-layer → plugin containers → project repos