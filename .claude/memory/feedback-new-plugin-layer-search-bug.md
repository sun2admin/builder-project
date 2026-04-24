---
name: new-plugin-layer search implementation (FIXED v3)
description: Search uses raw GitHub URLs for all 5 marketplaces, substring matching anywhere in name/description
type: feedback
originSessionId: e6384b3e-ac51-4f33-8f44-0569a8ce8ee7
---
**FIXED v3**: Search implementation in `scripts/plugin-search.sh` now:
- Queries all 5 available marketplaces including community (1636 plugins)
- Fetches marketplace.json via raw GitHub URLs (avoids API size limits for large repos)
- Uses `contains($term)` with `ascii_downcase` for simple substring matching (case-insensitive)
- Finds the term anywhere in plugin name OR description
- Returns aggregated results from all marketplaces

**Why v3:** Community marketplace (1636 plugins) was inaccessible via gh API due to size limits. Switched to raw GitHub URLs (`https://raw.githubusercontent.com/...`) which handle large files properly.

Test results:
- "git" → 128 results (official: 3, community: 125)
- "gh" → 29+ results (includes any plugin with "gh" in name/description across all marketplaces)
- "docker" → 18 results (community marketplace)
- "search" → 40+ results (official: 24, knowledge-work: 16, etc.)
