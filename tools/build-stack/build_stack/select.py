"""Phase 5a — L1 capability cover and L3 plugin layer selection.

L1: capability set algebra. Pick smallest L1 variant whose `provides` covers
the aggregated `required_caps`. User override allowed only if it still covers.

L3: match required `claude_plugins` against the recommended L3 image when
`use_recommended_l3` is set; otherwise return empty (plugins are delivered
via devcontainer features per the hybrid plugin-delivery architecture in
build-workflow-stack-composition.md amendment 2026-05-06).

See `.claude/plans/build-workflow-stack-composition.md` §2 and §4.
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


_CHROMIUM_KEYS = ("chromium", "chrome", "puppeteer-core", "puppeteer")
_FIREFOX_KEYS = ("firefox", "playwright-firefox", "geckodriver")
_WEBKIT_KEYS = ("webkit", "safari", "playwright-webkit")
_GRAPHICS_KEYS = ("cairo", "pango", "gtk", "wxgtk", "xvfb")
_DEV_TOOL_KEYS = ("gcc", "g++", "make", "cmake", "clang")


def _signals(agg: dict) -> set[str]:
    out: set[str] = set()
    for v in agg.get("browser_tools") or []:
        out.add(str(v).lower())
    libs = agg.get("libraries") or {}
    for v in libs.get("node") or []:
        out.add(str(v).lower())
    for v in libs.get("python") or []:
        out.add(str(v).lower())
    for v in agg.get("system_packages") or []:
        out.add(str(v).lower())
    inferred = agg.get("inferred") or {}
    for v in inferred.get("tools") or []:
        out.add(str(v).lower())
    return out


def _matches_any(signals: set[str], keys: tuple[str, ...]) -> bool:
    return any(k in s for s in signals for k in keys)


def uses_chromium(agg: dict) -> bool:
    return _matches_any(_signals(agg), _CHROMIUM_KEYS)


def uses_firefox(agg: dict) -> bool:
    return _matches_any(_signals(agg), _FIREFOX_KEYS)


def uses_webkit(agg: dict) -> bool:
    return _matches_any(_signals(agg), _WEBKIT_KEYS)


def needs_graphics(agg: dict) -> bool:
    sig = _signals(agg)
    if _matches_any(sig, _GRAPHICS_KEYS):
        return True
    return bool(agg.get("browser_tools"))


def needs_dev_tools(agg: dict) -> bool:
    return _matches_any(_signals(agg), _DEV_TOOL_KEYS)


def required_caps(agg: dict) -> set[str]:
    caps: set[str] = {"node", "shell"}
    languages = agg.get("languages") or []
    if "python" in languages:
        caps.add("python")
    browser_tools = agg.get("browser_tools") or []
    has_playwright = "playwright" in browser_tools
    if has_playwright:
        caps.add("playwright-core")
    chromium = uses_chromium(agg)
    firefox = uses_firefox(agg)
    webkit = uses_webkit(agg)
    if chromium:
        caps.add("chromium")
    if firefox:
        caps.add("firefox")
    if webkit:
        caps.add("webkit")
    if has_playwright and not (chromium or firefox or webkit):
        caps.add("chromium")
    if needs_graphics(agg):
        caps.add("graphics-libs")
    if needs_dev_tools(agg):
        caps.add("dev-tools")
    return caps


def pick_l1(agg: dict) -> tuple[str, list[str]]:
    needed = required_caps(agg)
    candidates = [
        (name, variant)
        for name, variant in L1_VARIANTS.items()
        if needed <= variant["provides"]
    ]
    if candidates:
        candidates.sort(key=lambda x: (x[1]["rank"], x[0]))
        return candidates[0][0], []
    max_rank = max(v["rank"] for v in L1_VARIANTS.values())
    fallback = sorted(
        ((n, v) for n, v in L1_VARIANTS.items() if v["rank"] == max_rank),
        key=lambda x: x[0],
    )[0]
    name, variant = fallback
    return name, sorted(needed - variant["provides"])


def validate_override(user_choice: str, agg: dict) -> tuple[bool, str | None]:
    if user_choice not in L1_VARIANTS:
        return False, f"unknown variant {user_choice!r}"
    needed = required_caps(agg)
    missing = needed - L1_VARIANTS[user_choice]["provides"]
    if missing:
        return False, (
            f"override {user_choice!r} missing required capabilities: "
            f"{sorted(missing)}"
        )
    return True, None


RECOMMENDED_L3_IMAGE = "ghcr.io/sun2admin/claude-plugins-recommended:latest"


def pick_l3_plugins(
    agg: dict,
    available_images: list[dict] | None = None,
    use_recommended_l3: bool = False,
) -> dict:
    """Pick the L3 base image.

    When use_recommended_l3 is True, the build bases on the recommended L3
    image (recommended-plugins.json baked in). Additional plugins from
    plugin_selections install via L4 features per CPQ1=(b).

    When False, falls back to the legacy plugin-set matching against
    available_images. The matching path is deprecated under the hybrid
    plugin delivery model and exists only for transitional builds.
    """
    if use_recommended_l3:
        return {"image": RECOMMENDED_L3_IMAGE, "missing": []}

    needed = set(agg.get("claude_plugins") or [])
    if not needed:
        return {"image": None, "missing": []}
    if not available_images:
        return {"image": None, "missing": sorted(needed)}
    candidates = [
        img for img in available_images
        if needed <= set(img.get("plugin_set") or [])
    ]
    if candidates:
        chosen = min(
            candidates,
            key=lambda i: (len(i.get("plugin_set") or []), i.get("name", "")),
        )
        return {"image": chosen.get("name"), "missing": []}
    return {"image": None, "missing": sorted(needed)}
