# layer1-ai-depends

Base container image with conditional tag variants for AI development environments.

## Tag Variants

| Tag | Size | Description |
|-----|------|-------------|
| `:light` | ~500MB | Node.js + Anthropic-recommended minimal packages |
| `:latest` | ~1.2GB | `:light` + Python + dev tools + graphics libraries |
| `:playwright_with_chromium` | ~1.45GB | `:latest` + Chromium browser |
| `:playwright_with_firefox` | ~1.4GB | `:latest` + Firefox browser |
| `:playwright_with_safari` | ~1.35GB | `:latest` + WebKit (Safari) browser |
| `:playwright_with_all` | — | ❌ Exceeds GitHub Actions runner time limit — do not build |

## Usage

In devcontainer.json:
```json
{
  "image": "ghcr.io/sun2admin/layer1-ai-depends:latest"
}
```

Or with Playwright:
```json
{
  "image": "ghcr.io/sun2admin/layer1-ai-depends:playwright_with_chromium"
}
```

## Build

Built via GitHub Actions matrix to produce all tag variants from single Dockerfile.
