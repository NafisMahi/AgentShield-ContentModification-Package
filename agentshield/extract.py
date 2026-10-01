"""Stage 2 (`extract`): read structured content from the local source.

The configured content source (agentshield/sources/) reads the project's
products/articles directly and returns them as page dicts. No browser, extraction
model, or network is involved. This module is a thin wrapper shared by the CLI's
add and extract stages.
"""
from __future__ import annotations

from .sources import get_source


def load_local(cfg) -> list[dict]:
    """Read all product/article pages from the local project via the configured source."""
    return get_source(cfg).load()


def index_by_url(pages) -> dict:
    return {p["url"]: p for p in pages}
