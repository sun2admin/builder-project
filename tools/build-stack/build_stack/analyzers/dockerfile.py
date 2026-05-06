"""Dockerfile + devcontainer.json scanners.

Detects: dockerfile_base, system_packages (apt-get install lines),
extra_binaries (curl/wget release downloads), global_js_packages,
dockerfile_python_installs, dockerfile_go_installs, ports.inbound (EXPOSE),
env_vars (ENV), container.capabilities (--cap-add via devcontainer.json
runArgs), container.volumes, container.env, container.post_start,
container.post_create, container.extensions.

Phase 2 stub — implementation pending detector port.
"""

from __future__ import annotations

from pathlib import Path

from .schema import AnalysisResult


def detect(repo_path: Path, result: AnalysisResult) -> None:
    """Mutate `result` in place with Dockerfile + devcontainer-derived fields.

    Phase 2 stub — raises NotImplementedError.
    """
    raise NotImplementedError("dockerfile.detect() pending — Phase 2 port work")
