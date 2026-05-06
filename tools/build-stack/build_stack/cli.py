"""CLI entry: argparse subcommand dispatch.

Subcommands map to phase modules. See README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_validate(args: argparse.Namespace) -> int:
    from build_stack import schema_validation
    return schema_validation.validate_build_json(Path(args.build_json))


def cmd_compose(args: argparse.Namespace) -> int:
    raise NotImplementedError(
        "Phase 3-6 pipeline not yet implemented. "
        "See .claude/plans/build-workflow-stack-composition.md migration step 6."
    )


def cmd_analyze(args: argparse.Namespace) -> int:
    """Single-repo detection. Phase 3 cutover: invokes the Python port
    directly (the analyze-repo skill is now a thin bash wrapper around
    this same entry point).

    stdout: path to analyzed_repos/<owner>/<repo>/analysis.json
    stderr: markdown report when emit enabled (TTY default; -v force; -q suppress)
    """
    from build_stack.analyzers import analyze as port_analyze, write_outputs
    from build_stack.analyzers import report

    data = port_analyze(args.repo)

    repo_root = Path(__file__).resolve().parents[3]
    out_dir = repo_root / "analyzed_repos" / args.repo
    json_path = write_outputs(data, out_dir)

    emit_md = args.human or (not args.quiet and sys.stdout.isatty())
    if emit_md:
        sys.stderr.write(report.render(data))

    print(json_path)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    raise NotImplementedError("`diff` subcommand is future scope.")


def cmd_stats(args: argparse.Namespace) -> int:
    raise NotImplementedError("`stats` subcommand is future scope.")


def cmd_rebuild(args: argparse.Namespace) -> int:
    raise NotImplementedError("`rebuild` subcommand is future scope.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build-stack")
    subs = parser.add_subparsers(dest="subcommand", required=True)

    p_validate = subs.add_parser("validate", help="Schema-check a build.json")
    p_validate.add_argument("build_json", help="Path to builds/<name>/build.json")
    p_validate.set_defaults(func=cmd_validate)

    p_compose = subs.add_parser("compose", help="Full Phase 3-6 pipeline")
    p_compose.add_argument("build_json", help="Path to builds/<name>/build.json")
    p_compose.add_argument("--dry-run", action="store_true")
    p_compose.set_defaults(func=cmd_compose)

    p_analyze = subs.add_parser("analyze", help="Standalone single-repo detection")
    p_analyze.add_argument("repo", help="owner/repo")
    g_analyze = p_analyze.add_mutually_exclusive_group()
    g_analyze.add_argument("--human", "-v", action="store_true", help="Force markdown emit on stderr")
    g_analyze.add_argument("--quiet", "-q", action="store_true", help="Suppress markdown emit")
    p_analyze.set_defaults(func=cmd_analyze)

    p_diff = subs.add_parser("diff", help="Stack-diff (future)")
    p_diff.add_argument("build_a")
    p_diff.add_argument("build_b")
    p_diff.set_defaults(func=cmd_diff)

    p_stats = subs.add_parser("stats", help="Promotion-path metrics (future)")
    p_stats.add_argument("builds_dir")
    p_stats.set_defaults(func=cmd_stats)

    p_rebuild = subs.add_parser("rebuild", help="Re-emit from existing build.json (future)")
    p_rebuild.add_argument("build_dir")
    p_rebuild.set_defaults(func=cmd_rebuild)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
