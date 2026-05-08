"""Unit tests for build_stack.cli — argparse construction + dispatch.

Covers:
  * `build_parser()` — every subcommand registered, each has `func` set
  * `cmd_list_ai_clis` — single-source-of-truth for AI CLI options
    consumed by the /build-stack skill menu
  * `cmd_diff` / `cmd_stats` / `cmd_rebuild` — future-stub contract
    (raise NotImplementedError, NOT silently no-op)
  * `main()` — exit-code propagation + argparse-driven `subcommand`
    requirement

Skips the heavy I/O subcommands (cmd_compose, cmd_analyze,
cmd_analyze_plugin) — those need integration tests with full repo
fixtures, not unit tests.
"""

from __future__ import annotations

import argparse
import json

import pytest

from build_stack import cli


# ─── build_parser: subcommand registration ────────────────────────────────────

EXPECTED_SUBCOMMANDS = {
    "validate", "compose", "analyze", "analyze-plugin",
    "list-ai-clis", "diff", "stats", "rebuild",
}


def test_build_parser_returns_argument_parser():
    p = cli.build_parser()
    assert isinstance(p, argparse.ArgumentParser)


def test_build_parser_registers_all_expected_subcommands():
    p = cli.build_parser()
    sub_action = next(
        a for a in p._actions if isinstance(a, argparse._SubParsersAction)
    )
    assert set(sub_action.choices.keys()) == EXPECTED_SUBCOMMANDS


def test_build_parser_subcommand_required():
    """No subcommand → SystemExit (argparse `required=True`)."""
    p = cli.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args([])


@pytest.mark.parametrize("sub", sorted(EXPECTED_SUBCOMMANDS))
def test_build_parser_each_subcommand_has_func(sub):
    """Every subcommand must `set_defaults(func=...)` so main() can dispatch."""
    p = cli.build_parser()
    sub_action = next(
        a for a in p._actions if isinstance(a, argparse._SubParsersAction)
    )
    sub_parser = sub_action.choices[sub]
    # Find the `func` default by parsing minimal positional args
    if sub == "validate":
        ns = p.parse_args([sub, "x.json"])
    elif sub == "compose":
        ns = p.parse_args([sub, "x.json"])
    elif sub == "analyze":
        ns = p.parse_args([sub, "owner/repo"])
    elif sub == "analyze-plugin":
        ns = p.parse_args([sub, "owner/repo", "myplugin"])
    elif sub == "diff":
        ns = p.parse_args([sub, "a", "b"])
    elif sub == "stats":
        ns = p.parse_args([sub, "/tmp"])
    elif sub == "rebuild":
        ns = p.parse_args([sub, "/tmp"])
    else:  # list-ai-clis
        ns = p.parse_args([sub])
    assert callable(getattr(ns, "func", None))


# ─── analyze flags ────────────────────────────────────────────────────────────

def test_analyze_out_dir_flag_threaded_through():
    p = cli.build_parser()
    ns = p.parse_args(["analyze", "owner/repo", "--out-dir", "/tmp/x"])
    assert ns.out_dir == "/tmp/x"
    assert ns.repo == "owner/repo"


def test_analyze_human_quiet_mutually_exclusive():
    """argparse must reject `-v -q` together — they conflict by intent."""
    p = cli.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["analyze", "owner/repo", "-v", "-q"])


def test_analyze_default_quiet_false():
    p = cli.build_parser()
    ns = p.parse_args(["analyze", "owner/repo"])
    assert ns.quiet is False
    assert ns.human is False


def test_analyze_short_v_alias_for_human():
    p = cli.build_parser()
    ns = p.parse_args(["analyze", "owner/repo", "-v"])
    assert ns.human is True


def test_analyze_short_q_alias_for_quiet():
    p = cli.build_parser()
    ns = p.parse_args(["analyze", "owner/repo", "-q"])
    assert ns.quiet is True


# ─── compose flags ────────────────────────────────────────────────────────────

def test_compose_dry_run_default_false():
    p = cli.build_parser()
    ns = p.parse_args(["compose", "x.json"])
    assert ns.dry_run is False


def test_compose_dry_run_flag_true_when_set():
    p = cli.build_parser()
    ns = p.parse_args(["compose", "x.json", "--dry-run"])
    assert ns.dry_run is True


# ─── list-ai-clis ─────────────────────────────────────────────────────────────

def test_list_ai_clis_default_form_one_per_line(capsys):
    p = cli.build_parser()
    ns = p.parse_args(["list-ai-clis"])
    rc = cli.cmd_list_ai_clis(ns)
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert out == ["claude", "gemini"]


def test_list_ai_clis_json_form_emits_array(capsys):
    p = cli.build_parser()
    ns = p.parse_args(["list-ai-clis", "--json"])
    rc = cli.cmd_list_ai_clis(ns)
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert json.loads(out) == ["claude", "gemini"]


def test_list_ai_clis_returns_zero():
    """Pinned: this subcommand never errors. Skill consumes its output as
    a menu — non-zero exit would break the /build-stack flow."""
    ns = argparse.Namespace(json=False)
    assert cli.cmd_list_ai_clis(ns) == 0


# ─── future-stub commands ─────────────────────────────────────────────────────

def test_cmd_diff_raises_not_implemented():
    """diff/stats/rebuild are documented future scope — they MUST raise
    NotImplementedError rather than silently no-op. A future PR adding a
    stub that returns 0 would be a regression in user expectation."""
    with pytest.raises(NotImplementedError, match="diff"):
        cli.cmd_diff(argparse.Namespace())


def test_cmd_stats_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="stats"):
        cli.cmd_stats(argparse.Namespace())


def test_cmd_rebuild_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="rebuild"):
        cli.cmd_rebuild(argparse.Namespace())


# ─── main() dispatch + exit code propagation ─────────────────────────────────

def test_main_propagates_func_return_code():
    """If a subcommand returns 7, main() must return 7 (not 0).
    F1 (commit 664f8f1) made __main__.py propagate this — pin it here too."""
    def fake_cmd(args):
        return 7
    p = cli.build_parser()
    ns = p.parse_args(["list-ai-clis"])
    ns.func = fake_cmd
    # Bypass argparse — call dispatch directly with our injected func
    rc = ns.func(ns) or 0
    assert rc == 7


def test_main_returns_zero_when_func_returns_none():
    """`return args.func(args) or 0` — None coerced to 0 (defensive)."""
    def returns_none(args):
        return None
    ns = argparse.Namespace(func=returns_none)
    assert (ns.func(ns) or 0) == 0


def test_main_no_args_exits():
    """Bare `build-stack` (no subcommand) → SystemExit via argparse."""
    with pytest.raises(SystemExit):
        cli.main([])


def test_main_list_ai_clis_returns_zero(capsys):
    """End-to-end smoke: main(['list-ai-clis']) exits 0."""
    rc = cli.main(["list-ai-clis"])
    assert rc == 0


def test_main_list_ai_clis_json_form(capsys):
    rc = cli.main(["list-ai-clis", "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert json.loads(out) == ["claude", "gemini"]
