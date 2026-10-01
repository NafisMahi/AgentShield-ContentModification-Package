"""Local content-source adapters (replace crawling with a direct project read)."""
from .base import ContentSource, get_source, normalize_content

__all__ = ["ContentSource", "get_source", "normalize_content"]
