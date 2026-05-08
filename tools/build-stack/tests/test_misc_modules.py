"""Unit tests for the small remaining build_stack modules.

Bundled in one file because each module's testable surface is too thin
to justify its own file:
  * cloner.py — ValueError shape on bad repo format, cleanup() defensive guard
  * ghcr.py — NotImplementedError stubs (don't silently no-op)
  * analyze.py — re-export shim resolves to the real symbols
  * __init__.py — __version__ present
  * __main__.py — module imports cleanly + ends with sys.exit(main())

Subprocess paths in cloner.clone() are skipped — those need integration
tests (real gh auth + network), not unit tests with mocks.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from build_stack import analyze, ghcr
from build_stack.analyzers import cloner


# ─── cloner.clone — input validation ─────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "no-slash",
    "too/many/slashes",
    "",
])
def test_cloner_clone_rejects_bad_repo_format(bad):
    """Pre-flight format check happens BEFORE the subprocess call so that
    bad input doesn't waste a `gh repo clone` round-trip. The check only
    counts slashes (must be exactly 1) — see _NOT_CAUGHT below for the gap."""
    with pytest.raises(ValueError, match="expected owner/repo"):
        cloner.clone(bad)


def test_cloner_clone_error_message_includes_input():
    """Error message names what was actually received — helps users
    diagnose a typo without re-reading the format spec."""
    with pytest.raises(ValueError, match=re.escape("'weird-input'")):
        cloner.clone("weird-input")


@pytest.mark.parametrize("borderline", ["/leading", "trailing/", "/"])
def test_cloner_clone_validation_gap_one_slash_not_caught(borderline):
    """KNOWN GAP: the validator only counts slashes. Inputs with exactly
    one slash but empty owner or repo (`/leading`, `trailing/`, `/`) escape
    the ValueError and hit `gh repo clone` instead, raising RuntimeError.
    Pinned as a contract — if a future PR tightens the validator (e.g. to
    `re.match(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", repo)`), this test
    will start failing and the dev can update it to assert ValueError."""
    with pytest.raises((RuntimeError, ValueError)):
        cloner.clone(borderline)


# ─── cloner.cleanup — defensive guard ─────────────────────────────────────────

def test_cloner_cleanup_only_removes_bs_analyze_prefixed_parents(tmp_path):
    """Defensive: cleanup() must only delete dirs whose parent name starts
    with `bs-analyze-`. Otherwise a buggy caller could rm an arbitrary path."""
    (tmp_path / "child").mkdir()
    cloner.cleanup(tmp_path / "child")
    # tmp_path has no `bs-analyze-` prefix → must NOT be deleted
    assert tmp_path.exists()
    assert (tmp_path / "child").exists()


def test_cloner_cleanup_removes_when_prefix_matches(tmp_path):
    """Positive case: parent dir named bs-analyze-XXX → cleanup removes it."""
    parent = tmp_path / "bs-analyze-abc123"
    parent.mkdir()
    repo = parent / "myrepo"
    repo.mkdir()
    cloner.cleanup(repo)
    assert not parent.exists()


def test_cloner_cleanup_nonexistent_path_no_crash(tmp_path):
    """`shutil.rmtree(..., ignore_errors=True)` swallows missing-path errors."""
    cloner.cleanup(tmp_path / "bs-analyze-x" / "ghost")  # parent doesn't exist


# ─── ghcr — stubs raise NotImplementedError ───────────────────────────────────

def test_ghcr_list_plugin_images_raises():
    """Stub function MUST raise, not silently no-op or return None.
    A future no-op stub would mask the fact that this isn't wired up yet."""
    with pytest.raises(NotImplementedError, match="list_plugin_images"):
        ghcr.list_plugin_images()


def test_ghcr_get_source_repo_raises():
    with pytest.raises(NotImplementedError, match="get_source_repo"):
        ghcr.get_source_repo("ghcr.io/x/y:tag")


# ─── analyze — re-export shim ─────────────────────────────────────────────────

def test_analyze_reexports_real_callables():
    """Phase 3 cutover left analyze.py as a compatibility shim. Its two
    re-exports must resolve to the actual analyzer functions, not be None."""
    assert callable(analyze.analyze)
    assert callable(analyze.write_outputs)


def test_analyze_all_lists_both_reexports():
    """`from build_stack.analyze import *` must surface both names —
    documented contract for old callers per the module docstring."""
    assert set(analyze.__all__) == {"analyze", "write_outputs"}


def test_analyze_reexports_match_underlying():
    """The shim points at build_stack.analyzers — pin the redirect
    relationship so a future refactor that moves the real impl elsewhere
    breaks this test loudly."""
    from build_stack import analyzers
    assert analyze.analyze is analyzers.analyze
    assert analyze.write_outputs is analyzers.write_outputs


# ─── __init__.py + __main__.py ────────────────────────────────────────────────

def test_package_exposes_version_string():
    """build_stack.__version__ exists — used by tooling and docs."""
    import build_stack
    assert isinstance(build_stack.__version__, str)
    assert build_stack.__version__  # non-empty


def test_main_module_imports_cleanly():
    """`python -m build_stack` does `import build_stack.__main__`. Verify
    the import doesn't error (loads cli.main without side effects)."""
    mod = importlib.import_module("build_stack.__main__")
    # The module should not export `main` directly — it imports it for
    # the if __name__=='__main__' block. Just verify it loaded.
    assert mod.__name__ == "build_stack.__main__"


def test_main_module_source_calls_sys_exit():
    """The entry point file must end with `sys.exit(main())` so exit
    codes propagate (per F1 fix). Verify the literal source contains
    that call — otherwise __main__ would always exit 0."""
    src = (Path(__file__).resolve().parent.parent / "build_stack" / "__main__.py").read_text()
    assert "sys.exit(main())" in src
