"""Unit tests for build_stack.select — L1 cover + L3 plugin selection.

Pure-function module: tests use inline literal ``agg`` dicts (no fixtures,
no tmp_path, no clones). Pins the contracts the /build-stack skill relies
on for UX (variant choice, missing-cap messaging, override validation,
recommended-L3 short-circuit).
"""

from __future__ import annotations

import pytest

from build_stack.select import (
    L1_VARIANTS,
    RECOMMENDED_L3_IMAGE,
    pick_l1,
    pick_l3_plugins,
    required_caps,
    validate_override,
    uses_chromium,
    uses_firefox,
    uses_webkit,
    needs_graphics,
    needs_dev_tools,
)


# ─── required_caps ────────────────────────────────────────────────────────────

def test_required_caps_default_node_and_shell():
    """Empty agg still requires node+shell — minimum L1 baseline."""
    assert required_caps({}) == {"node", "shell"}


def test_required_caps_python_language_adds_python():
    caps = required_caps({"languages": ["python"]})
    assert "python" in caps


def test_required_caps_browser_tools_imply_graphics():
    caps = required_caps({"browser_tools": ["playwright"]})
    assert "graphics-libs" in caps


def test_required_caps_playwright_default_browser_is_chromium():
    """When playwright is detected but no browser signals → chromium default."""
    caps = required_caps({"browser_tools": ["playwright"]})
    assert "chromium" in caps
    assert "playwright-core" in caps


def test_required_caps_playwright_with_explicit_firefox_does_not_add_chromium():
    caps = required_caps({
        "browser_tools": ["playwright"],
        "libraries": {"node": ["playwright-firefox"]},
    })
    assert "firefox" in caps
    assert "chromium" not in caps


def test_required_caps_dev_tools_from_system_packages():
    caps = required_caps({"system_packages": ["gcc", "make"]})
    assert "dev-tools" in caps


# ─── signal predicates (substring matching) ──────────────────────────────────

def test_uses_chromium_matches_substring_in_node_lib():
    """Substring match: 'playwright-chromium' contains 'chromium'."""
    agg = {"libraries": {"node": ["playwright-chromium"]}}
    assert uses_chromium(agg) is True


def test_uses_firefox_via_geckodriver_signal():
    agg = {"libraries": {"python": ["geckodriver-py"]}}
    assert uses_firefox(agg) is True


def test_uses_webkit_via_safari_alias():
    agg = {"inferred": {"tools": ["safari-driver"]}}
    assert uses_webkit(agg) is True


def test_needs_graphics_true_when_browser_tools_present():
    """Browser presence → graphics-libs even without explicit gtk/cairo."""
    assert needs_graphics({"browser_tools": ["playwright"]}) is True


def test_needs_dev_tools_false_for_empty_agg():
    assert needs_dev_tools({}) is False


# ─── pick_l1 ──────────────────────────────────────────────────────────────────

def test_pick_l1_empty_agg_picks_light():
    """Smallest-covering rule: only node+shell needed → 'light' (rank 1)."""
    name, missing = pick_l1({})
    assert name == "light"
    assert missing == []


def test_pick_l1_python_forces_latest():
    """'light' excludes python → must climb to 'latest' (rank 2)."""
    name, missing = pick_l1({"languages": ["python"]})
    assert name == "latest"
    assert missing == []


def test_pick_l1_dev_tools_forces_latest():
    """gcc signal pushes past 'light' (light lacks dev-tools)."""
    name, missing = pick_l1({"system_packages": ["gcc"]})
    assert name == "latest"
    assert missing == []


def test_pick_l1_playwright_chromium_picks_chromium_variant():
    name, missing = pick_l1({
        "browser_tools": ["playwright"],
        "libraries": {"node": ["playwright-chromium"]},
    })
    assert name == "playwright_with_chromium"
    assert missing == []


def test_pick_l1_playwright_firefox_picks_firefox_variant():
    name, missing = pick_l1({
        "browser_tools": ["playwright"],
        "libraries": {"node": ["playwright-firefox"]},
    })
    assert name == "playwright_with_firefox"
    assert missing == []


def test_pick_l1_playwright_webkit_picks_safari_variant():
    name, missing = pick_l1({
        "browser_tools": ["playwright"],
        "libraries": {"node": ["playwright-webkit"]},
    })
    assert name == "playwright_with_safari"
    assert missing == []


def test_pick_l1_playwright_no_browser_defaults_to_chromium():
    """No explicit browser hint → required_caps adds chromium → chromium variant."""
    name, missing = pick_l1({"browser_tools": ["playwright"]})
    assert name == "playwright_with_chromium"
    assert missing == []


def test_pick_l1_multi_browser_no_covering_variant_returns_fallback_with_missing():
    """playwright_with_all is unpublished → multi-browser must fall back."""
    name, missing = pick_l1({
        "browser_tools": ["playwright"],
        "libraries": {"node": ["playwright-chromium", "playwright-firefox"]},
    })
    assert name in {
        "playwright_with_chromium",
        "playwright_with_firefox",
        "playwright_with_safari",
    }
    assert missing
    assert all(isinstance(m, str) for m in missing)
    assert missing == sorted(missing)


def test_pick_l1_tie_broken_by_rank_then_name():
    """When multiple covering candidates exist, lowest rank wins; then alpha."""
    name, _ = pick_l1({})
    expected_rank = min(v["rank"] for v in L1_VARIANTS.values())
    assert L1_VARIANTS[name]["rank"] == expected_rank


# ─── validate_override ────────────────────────────────────────────────────────

def test_validate_override_unknown_variant_rejected():
    ok, err = validate_override("nonexistent", {})
    assert ok is False
    assert err is not None
    assert "unknown" in err.lower()


def test_validate_override_known_variant_covering_caps_accepted():
    ok, err = validate_override("latest", {"languages": ["python"]})
    assert ok is True
    assert err is None


def test_validate_override_variant_missing_caps_rejected_with_list():
    """User picks 'light' for a python project → must be rejected with details."""
    ok, err = validate_override("light", {"languages": ["python"]})
    assert ok is False
    assert err is not None
    assert "python" in err
    assert "missing" in err.lower()


# ─── pick_l3_plugins ──────────────────────────────────────────────────────────

def test_pick_l3_use_recommended_returns_canonical_image():
    """use_recommended_l3=True short-circuits; available_images ignored."""
    out = pick_l3_plugins({}, available_images=None, use_recommended_l3=True)
    assert out == {"image": RECOMMENDED_L3_IMAGE, "missing": []}


def test_pick_l3_use_recommended_ignores_claude_plugins_list():
    """Recommended path baselines plugins via the prebuilt image — extras
    are delivered via L4 features, so claude_plugins is irrelevant here."""
    out = pick_l3_plugins(
        {"claude_plugins": ["foo", "bar"]},
        available_images=None,
        use_recommended_l3=True,
    )
    assert out["image"] == RECOMMENDED_L3_IMAGE
    assert out["missing"] == []


def test_pick_l3_no_claude_plugins_no_image():
    """No plugins requested → no image, no missing."""
    out = pick_l3_plugins({}, available_images=None, use_recommended_l3=False)
    assert out == {"image": None, "missing": []}


def test_pick_l3_plugins_needed_no_images_returns_missing_sorted():
    out = pick_l3_plugins(
        {"claude_plugins": ["zulu", "alpha", "mike"]},
        available_images=None,
        use_recommended_l3=False,
    )
    assert out["image"] is None
    assert out["missing"] == ["alpha", "mike", "zulu"]


def test_pick_l3_picks_smallest_covering_image():
    """Tie-break: covering image with fewest plugins wins (less surface area)."""
    images = [
        {"name": "big", "plugin_set": ["a", "b", "c", "d"]},
        {"name": "tight", "plugin_set": ["a", "b"]},
    ]
    out = pick_l3_plugins(
        {"claude_plugins": ["a", "b"]},
        available_images=images,
        use_recommended_l3=False,
    )
    assert out == {"image": "tight", "missing": []}


def test_pick_l3_no_covering_image_returns_missing():
    images = [{"name": "partial", "plugin_set": ["a"]}]
    out = pick_l3_plugins(
        {"claude_plugins": ["a", "b"]},
        available_images=images,
        use_recommended_l3=False,
    )
    assert out == {"image": None, "missing": ["a", "b"]}


def test_pick_l3_tie_size_broken_by_name():
    """When two covering images have the same plugin_set size → alpha wins."""
    images = [
        {"name": "zebra", "plugin_set": ["a", "b"]},
        {"name": "alpha", "plugin_set": ["a", "b"]},
    ]
    out = pick_l3_plugins(
        {"claude_plugins": ["a"]},
        available_images=images,
        use_recommended_l3=False,
    )
    assert out["image"] == "alpha"
