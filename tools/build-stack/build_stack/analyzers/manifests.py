"""Language manifest parsers.

Detects: languages, runtime_versions, libraries{.node,.python,.go,.rust},
runtime_extras (e.g. playwright), browser_tools.

Sources scanned (per analyze-repo SKILL.md):
    package.json, requirements.txt, Pipfile, pyproject.toml, setup.py,
    Gemfile, go.mod, Cargo.toml, pom.xml, build.gradle, composer.json,
    .nvmrc, .python-version

Phase 2 stub — implementation pending detector port.
"""

from __future__ import annotations

from pathlib import Path

from .schema import AnalysisResult


def detect(repo_path: Path, result: AnalysisResult) -> None:
    """Mutate `result` in place with manifest-derived fields.

    Phase 2 stub — raises NotImplementedError.
    """
    raise NotImplementedError("manifests.detect() pending — Phase 2 port work")
