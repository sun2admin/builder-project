# ─── Stage 1: Binary downloader ──────────────────────────────────────────────
FROM node:20 AS downloader

ARG GIT_DELTA_VERSION=0.18.2
ARG HADOLINT_VERSION=2.12.0

RUN ARCH=$(dpkg --print-architecture) && \
    wget -q "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" \
         -O /tmp/git-delta.deb && \
    dpkg -i /tmp/git-delta.deb && \
    rm /tmp/git-delta.deb

RUN wget -q -O /usr/local/bin/hadolint \
    "https://github.com/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}/hadolint-Linux-x86_64" && \
    chmod +x /usr/local/bin/hadolint


# ─── Stage 2: Python venv builder ────────────────────────────────────────────
FROM node:20 AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    libffi-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir \
    jupyterlab \
    ipykernel \
    pdfplumber \
    pymupdf \
    pypdf \
    reportlab \
    weasyprint \
    pandas \
    numpy


# ─── Final image ──────────────────────────────────────────────────────────────
FROM node:20-slim

ARG TZ=America/New_York
ENV TZ="$TZ"

# Install runtime packages only — no build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    # shell and basic tools
    wget \
    curl \
    less \
    git \
    procps \
    sudo \
    fzf \
    man-db \
    unzip \
    gnupg2 \
    gh \
    # networking and firewall
    iptables \
    ipset \
    iproute2 \
    dnsutils \
    aggregate \
    # editors and utilities
    jq \
    nano \
    vim \
    passwd \
    openssh-client \
    # claude usability tools
    ripgrep \
    fd-find \
    tree \
    bat \
    shellcheck \
    sqlite3 \
    htop \
    # python runtime
    python3 \
    python3-pip \
    python3-venv \
    # pdf cli tools
    poppler-utils \
    pandoc \
    # weasyprint runtime dependencies
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy binaries from downloader stage
COPY --from=downloader /usr/bin/delta /usr/local/bin/delta
COPY --from=downloader /usr/local/bin/hadolint /usr/local/bin/hadolint

# Copy Python venv from python-builder stage
COPY --from=python-builder /opt/venv /opt/venv
RUN chmod -R a+rX /opt/venv

# Create symlinks for tools with non-standard Debian binary names
RUN ln -s "$(which fdfind)" /usr/local/bin/fd && \
    ln -s "$(which batcat)" /usr/local/bin/bat

# Make venv available system-wide
ENV PATH="/opt/venv/bin:$PATH"

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

WORKDIR /workspace

# Copy firewall init script
COPY init-firewall.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-firewall.sh
