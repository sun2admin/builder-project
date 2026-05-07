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
    """Run Phase 4-6 pipeline: aggregate → select → compose → emit.

    Reads build.json from `args.build_json`. Outputs (aggregated.json,
    devcontainer.json, workspace.env) land alongside the input file in
    its parent dir (skill controls placement via staging dir).
    """
    from build_stack import aggregate, select, compose, emit

    build_path = Path(args.build_json)
    build_data = json.loads(build_path.read_text())
    out_dir = build_path.parent
    repo_root = Path(__file__).resolve().parents[3]

    if args.dry_run:
        print(json.dumps(build_data, indent=2, sort_keys=True))
        return 0

    agg = aggregate.aggregate(build_data, repo_root)

    l1_variant, l1_extras = select.pick_l1(agg)
    l3_pick = select.pick_l3_plugins(
        agg,
        available_images=None,
        use_recommended_l3=bool(build_data.get("use_recommended_l3", False)),
    )
    l2_cli = (build_data.get("ai_clis") or ["claude"])[0]

    cresult = compose.compose_l4(agg, l1_variant, l1_extras, build_data, repo_root)

    emit.write_aggregated(agg, out_dir)
    emit.write_devcontainer(agg, l1_variant, l2_cli, l3_pick["image"], cresult, build_data, out_dir)
    emit.write_workspace_env(agg, l1_variant, l2_cli, l3_pick["image"], build_data, out_dir)

    print(out_dir / "devcontainer.json")
    return 0


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


def cmd_analyze_plugin(args: argparse.Namespace) -> int:
    """Single-plugin detection (sparse-checkout from a marketplace).

    Outputs analyzed_repos/plugins/<mkt_owner>/<mkt_repo>/<plugin>/analysis.json
    and prints its path on stdout. The marketplace.json is fetched + cached
    on first use under analyzed_repos/marketplaces/<owner>/<repo>/.
    """
    from build_stack.analyzers import plugin as plugin_mod

    repo_root = Path(__file__).resolve().parents[3]
    data = plugin_mod.analyze_plugin(args.marketplace, args.plugin, repo_root=repo_root)
    json_path = plugin_mod.write_plugin_outputs(data, repo_root, args.marketplace, args.plugin)
    print(json_path)
    return 0


def cmd_list_ai_clis(args: argparse.Namespace) -> int:
    """Return valid AI CLI choices for the skill's AI CLI menu.

    Single source of truth for L2 AI CLI options. Skill consumes this so
    new CLIs (gemini, future variants) only need to register here.
    """
    clis = ["claude", "gemini"]
    if args.json:
        print(json.dumps(clis))
    else:
        for c in clis:
            print(c)
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

    p_analyze_plugin = subs.add_parser("analyze-plugin", help="Sparse-checkout + analyze single plugin from a marketplace")
    p_analyze_plugin.add_argument("marketplace", help="owner/repo of marketplace (must be in marketplaces.json)")
    p_analyze_plugin.add_argument("plugin", help="plugin name (must exist in marketplace.json)")
    p_analyze_plugin.set_defaults(func=cmd_analyze_plugin)

    p_list_ai = subs.add_parser("list-ai-clis", help="List valid AI CLI choices for /build-stack skill menu")
    p_list_ai.add_argument("--json", action="store_true", help="Emit JSON array on stdout")
    p_list_ai.set_defaults(func=cmd_list_ai_clis)

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
