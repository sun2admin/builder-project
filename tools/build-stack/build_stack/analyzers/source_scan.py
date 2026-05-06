"""Source-tree inference: tool calls + imports.

Detects: inferred.tools / tools_new / tools_confirmed,
inferred.py_imports / ts_imports / ci_tools, external_services
(when source = source_scan), browser_tools (via library imports),
github_api_usage.

Per `.claude/skills/analyze-repo/DETECTION_PRINCIPLES.md`: derive from
artifacts, never compare against an opinion list. Use
`sys.stdlib_module_names` and Node's `node -e builtinModules` for
language-stdlib filtering.

Phase 2 stub — implementation pending detector port.
"""

from __future__ import annotations

from pathlib import Path

from .schema import AnalysisResult


def detect(repo_path: Path, result: AnalysisResult) -> None:
    """Mutate `result` in place with source-scan-derived fields.

    Phase 2 stub — raises NotImplementedError.
    """
    raise NotImplementedError("source_scan.detect() pending — Phase 2 port work")
