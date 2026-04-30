# base-ai-layer: Conditional tag variants for AI development
# Builds: :light, :latest, :playwright_with_chromium, :playwright_with_firefox,
#         :playwright_with_webkit, :playwright_with_all

FROM node:22-slim AS base

ARG TZ=America/New_York
ARG TARGETARCH
ENV TZ="$TZ"

# ─── Layer 1: Always install :light (Anthropic-recommended minimal packages) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl less git procps sudo fzf man-db unzip gnupg2 \
    iptables ipset iproute2 dnsutils aggregate \
    jq nano vim passwd openssh-client \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


# ─── Layer 2: Conditionally add :latest extras (dev tools, Python, graphics) ──
ARG INCLUDE_EXTRAS=false

RUN if [ "$INCLUDE_EXTRAS" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
    ripgrep fd-find tree bat shellcheck sqlite3 htop \
    python3 python3-pip python3-venv \
    poppler-utils pandoc \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
    jupyterlab ipykernel pdfplumber pymupdf pypdf \
    reportlab weasyprint pandas numpy && \
    ARCH=${TARGETARCH:-$(dpkg --print-architecture)} && \
    if [ "$ARCH" = "arm64" ]; then \
        DELTA_ARCH="aarch64-unknown-linux-gnu"; \
        HADOLINT_ARCH="arm64"; \
    else \
        DELTA_ARCH="x86_64-unknown-linux-gnu"; \
        HADOLINT_ARCH="x86_64"; \
    fi && \
    curl -sL https://github.com/dandavison/delta/releases/download/0.18.2/delta-0.18.2-${DELTA_ARCH}.tar.gz \
      | tar xz --strip-components=1 -C /usr/local/bin && \
    curl -sL https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-${HADOLINT_ARCH} \
      -o /usr/local/bin/hadolint && chmod +x /usr/local/bin/hadolint && \
    ln -s /usr/bin/fdfind /usr/local/bin/fd && \
    ln -s /usr/bin/batcat /usr/local/bin/bat; \
fi

ENV PATH="/opt/venv/bin:$PATH"


# ─── Stage: Playwright browser installer ─────────────────────────────────────────────
FROM node:22 AS playwright-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages playwright

ARG BROWSERS=chromium
RUN mkdir -p /root/.cache/ms-playwright && \
    for browser in $BROWSERS; do \
    python3 -m playwright install "$browser"; \
done


# ─── Layer 3: Conditionally add Playwright support ─────────────────────────────────────────
FROM base AS final

ARG INCLUDE_PLAYWRIGHT=false
ARG BROWSERS=chromium

COPY --from=playwright-builder /root/.cache/ms-playwright /tmp/playwright-cache

RUN if [ "$INCLUDE_PLAYWRIGHT" = "true" ]; then \
    rm -f /etc/apt/sources.list.d/github-cli.list && \
    mkdir -p /home/node/.cache/ms-playwright && \
    cp -r /tmp/playwright-cache/* /home/node/.cache/ms-playwright/ && \
    /opt/venv/bin/pip install --no-cache-dir playwright && \
    for browser in $BROWSERS; do \
        /opt/venv/bin/playwright install-deps "$browser"; \
    done; \
fi

ENV PLAYWRIGHT_BROWSERS_PATH=/home/node/.cache/ms-playwright
ENV PLAYWRIGHT_CHROMIUM_SANDBOX=0


# ─── Final setup ────────────────────────────────────────────────────────────────────────
ENV DEVCONTAINER=true
WORKDIR /workspace

COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh
