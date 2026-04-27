---
name: GHCR Images Always Private
description: All container images pushed to GHCR must always be private unless explicitly stated otherwise
type: feedback
---

All GHCR images must always be set to private visibility.

**Why:** User preference — never expose container images publicly.

**How to apply:** When creating GitHub Actions workflows that push to GHCR, verify the repo is private so the image inherits private visibility. After first push always verify in GitHub → Packages settings. Never suggest public visibility.