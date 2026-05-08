"""Unit tests for .claude/hooks/lib/tokens.py.

Covers the most-recent-entry contract that's load-bearing for the two
callers (context-warn.sh, statusline.sh): a max-tracker lost track of
real context size after `/compact` because the compact API call itself
recorded the full pre-compact context as a single huge entry. Tracking
the LAST entry naturally falls back after each compaction.

Run from the repo root:
    python3 -m pytest .claude/hooks/lib/test_tokens.py -v

The helper has no other test infrastructure — it lives next to its code
because the rest of the .claude/ tree is bash + plans, not Python.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Import the module from its actual location (sibling file).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tokens  # noqa: E402


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_jsonl(tmp_path: Path, entries: list[dict]) -> Path:
    """Write a Claude Code transcript JSONL given a list of message dicts."""
    p = tmp_path / "transcript.jsonl"
    with p.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return p


def _usage_entry(cr: int = 0, cc: int = 0, it: int = 0) -> dict:
    return {"message": {"role": "assistant", "usage": {
        "cache_read_input_tokens": cr,
        "cache_creation_input_tokens": cc,
        "input_tokens": it,
    }}}


# ─── extract() — pure function ────────────────────────────────────────────────

def test_extract_missing_file_returns_zeros(tmp_path):
    assert tokens.extract(str(tmp_path / "no-such-file.jsonl")) == (0, 0, 0)


def test_extract_directory_returns_zeros(tmp_path):
    """Path is a directory, not a file → IsADirectoryError caught."""
    assert tokens.extract(str(tmp_path)) == (0, 0, 0)


def test_extract_empty_file_returns_zeros(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    assert tokens.extract(str(p)) == (0, 0, 0)


def test_extract_single_usage_entry(tmp_path):
    p = _make_jsonl(tmp_path, [_usage_entry(cr=1000, cc=200, it=50)])
    assert tokens.extract(str(p)) == (1000, 200, 50)


def test_extract_returns_LAST_entry_not_max(tmp_path):
    """The load-bearing contract. The /compact summarization API call
    creates one giant entry (max). After /compact, real conversation
    starts much smaller. Tracking max would stick at the giant value
    forever; tracking last falls back naturally."""
    p = _make_jsonl(tmp_path, [
        _usage_entry(cr=265000, cc=100, it=1),   # the /compact entry — huge
        _usage_entry(cr=5000, cc=200, it=50),    # post-compact, small
        _usage_entry(cr=8000, cc=300, it=100),   # most recent
    ])
    assert tokens.extract(str(p)) == (8000, 300, 100)


def test_extract_skips_lines_without_message_usage(tmp_path):
    """User turns and tool-use entries don't have `message.usage` — they
    must be skipped, not treated as zeros that overwrite earlier values."""
    p = _make_jsonl(tmp_path, [
        _usage_entry(cr=5000, cc=100, it=10),
        {"message": {"role": "user", "content": "hi"}},  # no .usage
        {"type": "tool_use_result", "data": "..."},      # no .message
    ])
    assert tokens.extract(str(p)) == (5000, 100, 10)


def test_extract_skips_malformed_json_lines(tmp_path):
    """A corrupt line in the middle of the transcript shouldn't break
    parsing — the rest of the lines must still be processed."""
    p = tmp_path / "transcript.jsonl"
    with p.open("w") as f:
        f.write(json.dumps(_usage_entry(cr=1000)) + "\n")
        f.write("{not valid json\n")
        f.write(json.dumps(_usage_entry(cr=2000)) + "\n")
    assert tokens.extract(str(p)) == (2000, 0, 0)


def test_extract_handles_missing_token_fields(tmp_path):
    """If the API returns usage without one of the three fields → 0
    default (the `or 0` coalesces None / 0 / missing-key)."""
    p = _make_jsonl(tmp_path, [
        {"message": {"usage": {"cache_read_input_tokens": 5000}}},
        # cache_creation + input_tokens missing
    ])
    assert tokens.extract(str(p)) == (5000, 0, 0)


def test_extract_handles_explicit_null_token_fields(tmp_path):
    """JSON null in any field → coalesced to 0 via `or 0`."""
    p = _make_jsonl(tmp_path, [
        {"message": {"usage": {
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": 100,
            "input_tokens": None,
        }}},
    ])
    assert tokens.extract(str(p)) == (0, 100, 0)


def test_extract_skips_non_dict_message(tmp_path):
    """`message` is sometimes a string (e.g. plain user content) — must
    not crash trying to .get('usage') on a string."""
    p = _make_jsonl(tmp_path, [
        {"message": "plain string content"},
        _usage_entry(cr=999),
    ])
    assert tokens.extract(str(p)) == (999, 0, 0)


def test_extract_skips_non_dict_usage(tmp_path):
    """Defensive: usage being not-a-dict shouldn't crash the loop."""
    p = tmp_path / "transcript.jsonl"
    with p.open("w") as f:
        f.write(json.dumps({"message": {"usage": "weird-string"}}) + "\n")
        f.write(json.dumps(_usage_entry(cr=42)) + "\n")
    assert tokens.extract(str(p)) == (42, 0, 0)


# ─── CLI form ──────────────────────────────────────────────────────────────────

_TOKENS_PY = Path(__file__).resolve().parent / "tokens.py"


def _run_cli(*args: str) -> tuple[int, str]:
    """Invoke `python3 tokens.py <args>` and return (returncode, stdout)."""
    r = subprocess.run(
        [sys.executable, str(_TOKENS_PY), *args],
        capture_output=True, text=True, timeout=10,
    )
    return r.returncode, r.stdout


def test_cli_no_arg_prints_zeros():
    rc, out = _run_cli()
    assert rc == 0
    assert out.strip() == "0 0 0"


def test_cli_empty_string_arg_prints_zeros():
    """`bash` invocations may pass empty string when transcript_path is unset
    (e.g. statusline.sh's transcript fallback). Must not crash."""
    rc, out = _run_cli("")
    assert rc == 0
    assert out.strip() == "0 0 0"


def test_cli_missing_file_prints_zeros():
    rc, out = _run_cli("/does/not/exist.jsonl")
    assert rc == 0
    assert out.strip() == "0 0 0"


def test_cli_valid_transcript_prints_three_ints(tmp_path):
    p = _make_jsonl(tmp_path, [_usage_entry(cr=1234, cc=56, it=7)])
    rc, out = _run_cli(str(p))
    assert rc == 0
    parts = out.strip().split()
    assert len(parts) == 3
    assert parts == ["1234", "56", "7"]


def test_cli_output_format_parseable_by_bash_read():
    """The bash callers do `read -r cr cc it < <(python3 tokens.py "$t")`.
    Verify the output format matches `read -r` expectations: three
    whitespace-separated integers on a single line."""
    rc, out = _run_cli()
    # Single line, three fields, integer-typed
    lines = out.splitlines()
    assert len(lines) == 1
    fields = lines[0].split()
    assert len(fields) == 3
    for f in fields:
        int(f)  # raises if not parseable
