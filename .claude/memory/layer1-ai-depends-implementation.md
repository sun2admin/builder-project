---
name: layer1-ai-depends Implementation Details
description: Single Dockerfile with conditional builds for tag variants; multi-stage playwright-builder; GitHub Actions matrix
type: project
originSessionId: 3f6f6192-aa5b-4f57-be58-35aa8808c6e4
---
## layer1-ai-depends Repo

**Repository**: `https://github.com/sun2admin/layer1-ai-depends`
**Source in builder-project**: `layer1-ai-depends/`

**Purpose**: Base system packages, Python, graphics libs, optional Playwright browsers. No AI tools or user config.

---

## Dockerfile Structure

**Single Dockerfile with three conditional sections:**

### Stage 1: playwright-builder (always runs)
```dockerfile
FROM node:22 AS playwright-builder
RUN apt-get install python3-pip
RUN python3 -m pip install --no-cache-dir --break-system-packages playwright
RUN mkdir -p /root/.cache/ms-playwright && \
    for browser in $BROWSERS; do \
    python3 -m playwright install "$browser"; \
done
```

- `--break-system-packages` safe in ephemeral build container
- Directory created even if BROWSERS is empty (:light variant)

### Base Stage: Always installs :light
```dockerfile
FROM node:22-slim AS base
RUN apt-get install -y --no-install-recommends \
    wget curl less git procps sudo fzf man-db unzip gnupg2 gh \
    iptables ipset iproute2 dnsutils aggregate \
    jq nano vim passwd openssh-client
```

### Conditionally installs :latest extras
```dockerfile
ARG INCLUDE_EXTRAS=false
RUN if [ "$INCLUDE_EXTRAS" = "true" ]; then \
    apt-get install -y ripgrep fd-find tree bat shellcheck sqlite3 htop \
    python3 python3-pip python3-venv poppler-utils pandoc \
    libcairo2 libpango-1.0-0 ... && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install jupyterlab pdfplumber pymupdf \
    reportlab weasyprint pandas numpy; \
fi
```

### Conditionally copies Playwright
```dockerfile
FROM base AS final
ARG INCLUDE_PLAYWRIGHT=false
COPY --from=playwright-builder /root/.cache/ms-playwright /tmp/playwright-cache
RUN if [ "$INCLUDE_PLAYWRIGHT" = "true" ]; then \
    cp -r /tmp/playwright-cache/* /home/node/.cache/ms-playwright/ && \
    /opt/venv/bin/playwright install-deps "$browser"; \
fi
```

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

**File**: `layer1-ai-depends/.github/workflows/build-and-push.yml` (in builder-project subdir, pushed to standalone repo)

Tags format: `ghcr.io/sun2admin/layer1-ai-depends:<variant>`

---

## Build Status

- ✅ :light
- ✅ :latest
- ✅ :playwright_with_chromium
- ✅ :playwright_with_firefox
- ✅ :playwright_with_safari
- ❌ :playwright_with_all — exceeds GitHub Actions runner time limit, do not attempt rebuild

Images are private on GHCR.

---

## Downstream Usage

**layer2-ai-install** Dockerfile:
```dockerfile
FROM ghcr.io/sun2admin/layer1-ai-depends:latest
```

**All 8 plugin layer Dockerfiles**:
```dockerfile
FROM ghcr.io/sun2admin/layer2-ai-install:claude
```

## GHCR Package Permissions

After first image build, manually grant read access on layer1-ai-depends package to `layer2-ai-install` repo only. Plugin repos access this layer indirectly through layer2-ai-install's package namespace.
