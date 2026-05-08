"""Curated list of real public GitHub repos used as analyze-repo fixtures.

Originally lived in `tests/test_analyze_parity.py` (deleted post-Phase-3
cutover; see commit log). The list is preserved here because it remains
useful as a fixture catalog for future evaluation work — most concretely,
the F8 v2 design-rule evaluation per
`.claude/plans/credentials-delivery.md` Resume conditions, which calls
for v1 warning data across 2+ corpus projects.

Selection rationale (carried forward from the original parity test):
- 3 Anthropic-owned repos covering the canonical stack (Claude Code,
  connect-rust, security-review)
- 7 community / personal repos exhibiting varied stack characteristics
  (multi-language, large dep trees, devcontainer present/absent, etc.)
- Both sun2admin/builder-project (this repo) and
  sun2admin/build-containers-with-claude (the L4-template-derived
  reference Layer 4 stack), which together demonstrate the "convention
  is owned by L4 template" finding from F8.

Add a repo here when introducing it as a fixture. Removing one means
losing a real-world test surface — only do so if the repo is gone from
GitHub or the analysis cache for it is intentionally dropped.
"""

CORPUS: list[str] = [
    "anthropics/claude-code",
    "anthropics/connect-rust",
    "anthropics/claude-code-security-review",
    "danielrosehill/claude-code-projects-index",
    "garrytan/gstack",
    "hesreallyhim/awesome-claude-code",
    "peterkrueck/claude-code-development-kit",
    "santifer/career-ops",
    "sun2admin/build-containers-with-claude",
    "sun2admin/builder-project",
]
