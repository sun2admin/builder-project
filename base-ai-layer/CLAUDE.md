# Layer 1: base-ai-layer

**Published image**: `ghcr.io/sun2admin/base-ai-layer`
**Base**: `node:22-slim`

## Tag Variants

| Tag | Description |
|---|---|
| `:light` | Node.js + Anthropic-recommended minimal packages only |
| `:latest` | `:light` + Python + dev tools + graphics libs |
| `:playwright_with_chromium` | `:latest` + Chromium pre-baked |
| `:playwright_with_firefox` | `:latest` + Firefox pre-baked |
| `:playwright_with_safari` | `:latest` + WebKit pre-baked |
| `:playwright_with_all` | `:latest` + all three browsers |

## Dockerfile Structure

Single Dockerfile produces all 6 variants via build ARGs:

- `INCLUDE_EXTRAS=true|false` — adds Python, dev tools, graphics libs (`:latest` vs `:light`)
- `INCLUDE_PLAYWRIGHT=true|false` — copies browser cache from playwright-builder stage
- `BROWSERS=chromium|firefox|webkit` — space-separated list for playwright variants

**Multi-stage build**:
1. `base` stage — always installs `:light` packages (apt + gh CLI)
2. `playwright-builder` stage — downloads and installs browsers (separate from base to avoid size bloat)
3. `final` stage — conditionally copies playwright cache from playwright-builder

## init-firewall.sh

Baked into this image at `/usr/local/bin/init-firewall.sh`. Configures iptables egress rules:
- Fetches GitHub IP ranges from `api.github.com/meta`
- Resolves and allowlists specific domains (Anthropic, npmjs, VSCode, sentry, statsig)
- Drops all other outbound traffic
- Requires `NET_ADMIN` and `NET_RAW` capabilities (`runArgs` in devcontainer.json)

The `claude` user is granted passwordless sudo for this script only (configured in Layer 2).

## GitHub Actions

`build-and-push.yml` — matrix builds all 6 variants in parallel on push to main when `Dockerfile` or `init-firewall.sh` changes. Pushes to GHCR (private).

## Key Constraints

- All GHCR images must be private
- `gh` CLI installed via official apt repo (not snap)
- Python venv at `/opt/venv` — PATH set system-wide
