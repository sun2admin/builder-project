"""GHCR manifest queries for L3 plugin discovery and source-repo lookup.

Reads `org.opencontainers.image.source` OCI label from plugin images to
derive the source repo URL — see plan §1 plugin source-repo discovery.
"""

from __future__ import annotations


def list_plugin_images() -> list:
    """Query GHCR for available `claude-plugins-*` images."""
    raise NotImplementedError("ghcr.list_plugin_images is a stub.")


def get_source_repo(image: str) -> str | None:
    """Read `org.opencontainers.image.source` from the image manifest.

    Returns the source repo URL, or None if the label is missing.
    """
    raise NotImplementedError("ghcr.get_source_repo is a stub.")
