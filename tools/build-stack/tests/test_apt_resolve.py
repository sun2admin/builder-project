"""Unit tests for build_stack.analyzers.apt_resolve.

Covers cache I/O round-trip, the cache-only contract during tests
(`BUILD_STACK_APT_LIVE` unset → no subprocess calls), and the
`apt_package=null` sentinel rule (cached negative results don't pollute
`result.system_deps`).

Tests monkeypatch `apt_resolve.cache_path` to point at `tmp_path`, so the
real `tools/build-stack/build_stack/data/tool-deps.json` is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_stack.analyzers import apt_resolve
from build_stack.analyzers.schema import AnalysisResult


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Redirect apt_resolve.cache_path to a per-test path under tmp_path."""
    p = tmp_path / "tool-deps.json"
    monkeypatch.setattr(apt_resolve, "cache_path", lambda: p)
    return p


@pytest.fixture
def offline(monkeypatch):
    """Ensure BUILD_STACK_APT_LIVE is unset for the duration of the test."""
    monkeypatch.delenv("BUILD_STACK_APT_LIVE", raising=False)


# ─── cache I/O ────────────────────────────────────────────────────────────────

def test_load_cache_missing_file_returns_empty(tmp_cache):
    """No file on disk → empty dict (not a crash)."""
    assert apt_resolve.load_cache() == {}


def test_load_cache_malformed_json_returns_empty(tmp_cache):
    """Parser-error tolerance: a corrupt cache shouldn't break analysis."""
    tmp_cache.write_text("{ this is not valid json")
    assert apt_resolve.load_cache() == {}


def test_save_then_load_round_trip(tmp_cache):
    cache = {
        "jq": {"apt_package": "jq", "apt_depends": ["libjq1"]},
        "prompt_length": {"apt_package": None, "apt_depends": []},
    }
    apt_resolve.save_cache(cache)
    assert apt_resolve.load_cache() == cache


def test_save_cache_writes_sorted_keys(tmp_cache):
    """sort_keys=True ensures the cache file diffs cleanly across runs."""
    apt_resolve.save_cache({
        "zulu": {"apt_package": None, "apt_depends": []},
        "alpha": {"apt_package": "alpha", "apt_depends": []},
    })
    text = tmp_cache.read_text()
    assert text.index('"alpha"') < text.index('"zulu"')


def test_save_cache_writes_trailing_newline(tmp_cache):
    apt_resolve.save_cache({"jq": {"apt_package": "jq", "apt_depends": []}})
    assert tmp_cache.read_text().endswith("\n")


# ─── resolve() — cache-only mode ──────────────────────────────────────────────

def test_resolve_offline_unknown_tool_does_not_populate_system_deps(tmp_cache, offline):
    """No cache + no live → tool resolves to null sentinel, system_deps stays empty."""
    result = AnalysisResult()
    result.inferred.tools = ["jq"]
    apt_resolve.resolve(Path("/unused"), result)
    assert result.system_deps == {}


def test_resolve_offline_does_not_write_cache_file(tmp_cache, offline):
    """When BUILD_STACK_APT_LIVE is unset, the cache is read but never written.
    Reason: tests/parity runs must be side-effect-free per sub-plan OQ5=(a)."""
    result = AnalysisResult()
    result.inferred.tools = ["new_tool_never_seen_before"]
    apt_resolve.resolve(Path("/unused"), result)
    assert not tmp_cache.exists()


def test_resolve_uses_cached_apt_package(tmp_cache, offline):
    apt_resolve.save_cache({
        "jq": {"apt_package": "jq", "apt_depends": ["libjq1", "libc6"]},
    })
    result = AnalysisResult()
    result.inferred.tools = ["jq"]
    apt_resolve.resolve(Path("/unused"), result)
    assert "jq" in result.system_deps
    assert result.system_deps["jq"].apt_package == "jq"
    assert result.system_deps["jq"].apt_depends == ["libjq1", "libc6"]


def test_resolve_skips_tools_with_null_apt_package(tmp_cache, offline):
    """Cached `apt_package: null` (sentinel "no apt match") → tool excluded.
    This prevents captured-by-mistake variable names from polluting system_deps."""
    apt_resolve.save_cache({
        "prompt_length": {"apt_package": None, "apt_depends": []},
        "jq":            {"apt_package": "jq", "apt_depends": []},
    })
    result = AnalysisResult()
    result.inferred.tools = ["prompt_length", "jq"]
    apt_resolve.resolve(Path("/unused"), result)
    assert "jq" in result.system_deps
    assert "prompt_length" not in result.system_deps


def test_resolve_dedups_across_tools_and_ci_tools(tmp_cache, offline):
    """`jq` listed in both .tools and .ci_tools → resolved exactly once."""
    apt_resolve.save_cache({"jq": {"apt_package": "jq", "apt_depends": []}})
    result = AnalysisResult()
    result.inferred.tools = ["jq"]
    result.inferred.ci_tools = ["jq"]
    apt_resolve.resolve(Path("/unused"), result)
    assert len(result.system_deps) == 1
    assert "jq" in result.system_deps


def test_resolve_processes_ci_tools_too(tmp_cache, offline):
    """ci_tools are part of the resolve set even if .tools is empty."""
    apt_resolve.save_cache({"gh": {"apt_package": "gh", "apt_depends": []}})
    result = AnalysisResult()
    result.inferred.ci_tools = ["gh"]
    apt_resolve.resolve(Path("/unused"), result)
    assert "gh" in result.system_deps


def test_resolve_apt_depends_is_independent_copy(tmp_cache, offline):
    """system_deps[t].apt_depends must not alias the cache list — mutating
    one must not corrupt the other (defensive copy at population time)."""
    apt_resolve.save_cache({
        "jq": {"apt_package": "jq", "apt_depends": ["libjq1"]},
    })
    result = AnalysisResult()
    result.inferred.tools = ["jq"]
    apt_resolve.resolve(Path("/unused"), result)
    result.system_deps["jq"].apt_depends.append("MUTATION")
    # Re-load cache from disk to verify it wasn't mutated through aliasing
    fresh = apt_resolve.load_cache()
    assert fresh["jq"]["apt_depends"] == ["libjq1"]


def test_resolve_empty_inputs_no_op(tmp_cache, offline):
    result = AnalysisResult()
    apt_resolve.resolve(Path("/unused"), result)
    assert result.system_deps == {}


def test_resolve_offline_records_negative_in_local_cache_only(tmp_cache, offline):
    """Even in offline mode, the in-memory cache picks up null sentinels for
    unseen tools — this is intentional to avoid re-checking on the next call
    in the same process. But: the file on disk is NOT written (verified above
    by `test_resolve_offline_does_not_write_cache_file`)."""
    apt_resolve.save_cache({})
    result = AnalysisResult()
    result.inferred.tools = ["never_seen_tool"]
    apt_resolve.resolve(Path("/unused"), result)
    assert "never_seen_tool" not in result.system_deps


# ─── cache_path location ──────────────────────────────────────────────────────

def test_cache_path_under_data_dir():
    """Real cache lives at build_stack/data/tool-deps.json — keep this contract
    so manual edits to the cache file find their way to the right place."""
    p = apt_resolve.cache_path()
    assert p.name == "tool-deps.json"
    assert p.parent.name == "data"
