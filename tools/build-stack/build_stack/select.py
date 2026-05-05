"""Phase 5a — L1 capability cover and L3 plugin layer selection.

L1: capability set algebra. Pick smallest L1 variant whose `provides` covers
the aggregated `required_caps`. User override allowed only if it still covers.

L3: query GHCR for `claude-plugins-*` images, pick smallest superset of
required plugin set, or trigger /new-plugin-layer.

See plan §2 and §4.
"""

from __future__ import annotations


L1_VARIANTS = {
    "light": {
        "rank": 1,
        "provides": {"node", "shell", "gh-cli", "apt-essentials"},
        "excludes": {"python", "graphics-libs", "browser-engines"},
    },
    "latest": {
        "rank": 2,
        "provides": {
            "node", "shell", "gh-cli", "apt-essentials",
            "python", "dev-tools", "graphics-libs",
        },
        "excludes": {"browser-engines"},
    },
    "playwright_with_chromium": {
        "rank": 3,
        "provides": {
            "node", "shell", "gh-cli", "apt-essentials",
            "python", "dev-tools", "graphics-libs",
            "playwright-core", "chromium",
        },
        "excludes": {"firefox", "webkit"},
    },
    "playwright_with_firefox": {
        "rank": 3,
        "provides": {
            "node", "shell", "gh-cli", "apt-essentials",
            "python", "dev-tools", "graphics-libs",
            "playwright-core", "firefox",
        },
        "excludes": {"chromium", "webkit"},
    },
    "playwright_with_safari": {
        "rank": 3,
        "provides": {
            "node", "shell", "gh-cli", "apt-essentials",
            "python", "dev-tools", "graphics-libs",
            "playwright-core", "webkit",
        },
        "excludes": {"chromium", "firefox"},
    },
    # NOTE: playwright_with_all defined in CI but NOT published — exceeds
    # GitHub Actions runner time limit. See plan §2.
}


def required_caps(aggregated: dict) -> set:
    """Derive required L1 capability set from aggregated analysis."""
    raise NotImplementedError("select.required_caps is a stub.")


def pick_l1(aggregated: dict) -> tuple:
    """Return (variant_name, missing_caps_list).

    missing_caps_list is empty when a covering variant exists; otherwise it
    contains capabilities not covered by any L1 variant — those must be
    installed via L4 features or init scripts.
    """
    raise NotImplementedError("select.pick_l1 is a stub. See plan §2 algorithm.")


def validate_override(user_choice: str, needed: set) -> tuple:
    """Return (valid: bool, error_message: str | None)."""
    raise NotImplementedError("select.validate_override is a stub.")


def pick_l3(aggregated: dict) -> str | None:
    """Pick L3 plugin image covering aggregated.claude_plugins.

    Returns image name or None if /new-plugin-layer build is required.
    """
    raise NotImplementedError("select.pick_l3 is a stub. See plan §4.")
