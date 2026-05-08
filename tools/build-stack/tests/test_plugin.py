"""Unit tests for build_stack.analyzers.plugin pure helpers + writer.

Covers the testable surface that doesn't require live subprocess calls
(`gh api`, `git clone`):
  * `_marketplace_cache_path` / `plugin_cache_dir` — cache layout per Q2
  * `_find_plugin_entry` — dict lookup with informative error
  * `_resolve_source` — three source-shape normalizations per Q3
  * `write_plugin_outputs` — output file shape + path

Skipped: `_fetch_marketplace_json`, `_load_marketplace_json`,
`_clone_sparse`, `analyze_plugin` — these wrap subprocess + filesystem
ops that need integration tests rather than per-helper unit tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_stack.analyzers import plugin


# ─── _marketplace_cache_path / plugin_cache_dir ───────────────────────────────

def test_marketplace_cache_path_layout():
    """Per Q2: analyzed_repos/marketplaces/<owner>/<repo>/marketplace.json."""
    root = Path("/repo")
    p = plugin._marketplace_cache_path(root, "anthropics/claude-code")
    assert p == root / "analyzed_repos" / "marketplaces" / "anthropics" / "claude-code" / "marketplace.json"


def test_plugin_cache_dir_layout():
    """Per Q2: analyzed_repos/plugins/<mkt_owner>/<mkt_repo>/<plugin>/."""
    root = Path("/repo")
    p = plugin.plugin_cache_dir(root, "anthropics/claude-code", "feature-dev")
    assert p == root / "analyzed_repos" / "plugins" / "anthropics" / "claude-code" / "feature-dev"


# ─── _find_plugin_entry ───────────────────────────────────────────────────────

def test_find_plugin_entry_returns_matching_dict():
    market = {"name": "mkt", "plugins": [
        {"name": "alpha", "description": "A"},
        {"name": "beta",  "description": "B"},
    ]}
    out = plugin._find_plugin_entry(market, "beta")
    assert out["description"] == "B"


def test_find_plugin_entry_missing_raises_value_error():
    market = {"name": "mkt", "plugins": [{"name": "alpha"}]}
    with pytest.raises(ValueError, match="not found"):
        plugin._find_plugin_entry(market, "nonexistent")


def test_find_plugin_entry_includes_marketplace_name_in_error():
    """Error message names the marketplace so the user knows which one to check."""
    market = {"name": "anthropics/claude-code", "plugins": []}
    with pytest.raises(ValueError, match="anthropics/claude-code"):
        plugin._find_plugin_entry(market, "ghost")


def test_find_plugin_entry_handles_unnamed_marketplace():
    """When `name` is absent → fallback `(unnamed)` literal in error."""
    market = {"plugins": []}
    with pytest.raises(ValueError, match="\\(unnamed\\)"):
        plugin._find_plugin_entry(market, "x")


def test_find_plugin_entry_skips_non_dict_entries():
    """Plugins list may contain garbage entries — skip them, don't crash."""
    market = {"name": "mkt", "plugins": [
        "string-not-dict",
        None,
        {"name": "real", "description": "D"},
    ]}
    out = plugin._find_plugin_entry(market, "real")
    assert out["description"] == "D"


# ─── _resolve_source: three source shapes (Q3) ────────────────────────────────

def test_resolve_source_string_dot_slash_prefix():
    """`source: "./feature-dev"` → kind=self, path=feature-dev, marketplace url."""
    out = plugin._resolve_source({"source": "./feature-dev"}, "anthropics/claude-code")
    assert out["kind"] == "self"
    assert out["path"] == "feature-dev"
    assert out["url"] == "https://github.com/anthropics/claude-code.git"
    assert out["ref"] == ""
    assert out["sha"] == ""


def test_resolve_source_string_bare_subdir():
    out = plugin._resolve_source({"source": "feature-dev"}, "owner/repo")
    assert out["kind"] == "self"
    assert out["path"] == "feature-dev"


def test_resolve_source_string_dot_or_empty_means_repo_root():
    """`source: "."` (or "") → path empty → use clone root, no sparse-checkout."""
    out = plugin._resolve_source({"source": "."}, "owner/repo")
    assert out["kind"] == "self"
    assert out["path"] == ""


def test_resolve_source_dict_full_shape():
    src_dict = {
        "source": "git-subdir",
        "url": "https://github.com/x/y.git",
        "path": "plugins/foo",
        "ref": "main",
        "sha": "abc123",
    }
    out = plugin._resolve_source({"source": src_dict}, "ignored/marketplace")
    assert out == {
        "kind": "git-subdir",
        "url": "https://github.com/x/y.git",
        "path": "plugins/foo",
        "ref": "main",
        "sha": "abc123",
    }


def test_resolve_source_dict_with_url_only():
    """Minimal dict source: url required, path/ref/sha can be empty."""
    out = plugin._resolve_source(
        {"source": {"source": "url", "url": "https://example.com/repo.git"}},
        "owner/repo",
    )
    assert out["url"] == "https://example.com/repo.git"
    assert out["path"] == ""
    assert out["ref"] == ""


def test_resolve_source_dict_strips_path_slashes():
    """Leading/trailing slashes on path stripped — sparse-checkout doesn't want them."""
    out = plugin._resolve_source(
        {"source": {"source": "git-subdir", "url": "https://x", "path": "/sub/dir/"}},
        "owner/repo",
    )
    assert out["path"] == "sub/dir"


def test_resolve_source_unrecognized_shape_raises():
    """Sources that aren't str or dict (e.g. list, None) → ValueError."""
    with pytest.raises(ValueError, match="unrecognized"):
        plugin._resolve_source({"source": ["bogus", "list"]}, "owner/repo")


def test_resolve_source_string_strips_leading_trailing_slashes():
    out = plugin._resolve_source({"source": "//feature/"}, "owner/repo")
    assert out["path"] == "feature"


# ─── write_plugin_outputs ─────────────────────────────────────────────────────

def test_write_plugin_outputs_creates_full_directory_path(tmp_path):
    data = {"repo": "owner/repo#plugin", "project": "plugin"}
    out = plugin.write_plugin_outputs(data, tmp_path, "owner/marketplace", "myplugin")
    assert out.parent.is_dir()
    assert out.name == "analysis.json"


def test_write_plugin_outputs_returns_json_path(tmp_path):
    out = plugin.write_plugin_outputs({"x": 1}, tmp_path, "o/m", "p")
    assert out.is_file()
    assert json.loads(out.read_text()) == {"x": 1}


def test_write_plugin_outputs_trailing_newline(tmp_path):
    out = plugin.write_plugin_outputs({"x": 1}, tmp_path, "o/m", "p")
    assert out.read_text().endswith("\n")


def test_write_plugin_outputs_under_correct_subtree(tmp_path):
    """Output path must match the layout of `plugin_cache_dir`."""
    out = plugin.write_plugin_outputs({}, tmp_path, "owner/mkt", "myplugin")
    expected = plugin.plugin_cache_dir(tmp_path, "owner/mkt", "myplugin") / "analysis.json"
    assert out == expected
