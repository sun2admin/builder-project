"""Compatibility shim: re-export `analyze` from `analyzers` package.

Phase 3 cutover collapsed the Phase 1 shell-out wrapper into the Python
port (`build_stack.analyzers`). This module remains as a re-export so
`compose.py` and other internal callers can continue importing
`from build_stack import analyze; analyze.analyze(repo)` unchanged.
"""

from __future__ import annotations

from build_stack.analyzers import analyze, write_outputs

__all__ = ["analyze", "write_outputs"]
