"""Markdown report emitter.

Renders an `AnalysisResult` (or its asdict form) into the human-readable
markdown summary written to `analyzed_repos/<owner>/<repo>/analysis.md`.

Phase 2 stub — implementation pending. Output must match the bash skill's
markdown structure to keep parity with existing analyzed_repos artifacts.
"""

from __future__ import annotations


def render(data: dict) -> str:
    """Return markdown report string for the analysis dict.

    Phase 2 stub — raises NotImplementedError until report logic lands.
    """
    raise NotImplementedError("report.render() pending — Phase 2 port work")
