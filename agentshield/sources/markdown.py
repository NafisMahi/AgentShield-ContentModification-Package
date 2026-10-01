"""Content source: Markdown files with YAML frontmatter.

Each product/article is one `.md` file: a YAML frontmatter header followed by the
body. This layout is used by static-site generators such as Next.js, Astro, Hugo,
Jekyll, Eleventy, and Gatsby.

    ---
    title: Raw Wildflower Honey
    price: $14.99
    category: Pantry
    availability: true
    ---
    Our Raw Wildflower Honey is cold-extracted and completely unfiltered...

Configuration (agentshield.config.json -> "source"):

    "source": {
      "type": "markdown",
      "root": ".",                      # project dir; collection dirs are relative to it
      "collections": [
        { "type": "product", "dir": "content/products", "pathTemplate": "/product/{slug}" },
        { "type": "article", "dir": "content/articles", "pathTemplate": "/article/{slug}" }
      ]
    }

Adapting to another site usually means changing `dir` and `pathTemplate`, plus the
aliases in sources/base.py if the frontmatter uses different key names.
"""
from __future__ import annotations

from pathlib import Path

from .base import normalize_content

_MD_EXTENSIONS = (".md", ".markdown", ".mdx")

DEFAULT_COLLECTIONS = [
    {"type": "product", "dir": "content/products", "pathTemplate": "/product/{slug}"},
    {"type": "article", "dir": "content/articles", "pathTemplate": "/article/{slug}"},
]


class MarkdownSource:
    def __init__(self, source_cfg: dict):
        self.root = Path(source_cfg.get("root", "."))
        self.collections = source_cfg.get("collections") or DEFAULT_COLLECTIONS
        self.base_url = (source_cfg.get("baseUrl") or "").rstrip("/")

    def load(self) -> list[dict]:
        pages: list[dict] = []
        seen_paths: set[str] = set()
        for coll in self.collections:
            ctype = coll.get("type", "other")
            directory = self.root / coll.get("dir", "")
            path_tmpl = coll.get("pathTemplate", "/{slug}")
            if not directory.is_dir():
                continue
            for md_path in sorted(directory.rglob("*")):
                if md_path.suffix.lower() not in _MD_EXTENSIONS or not md_path.is_file():
                    continue
                page = self._read_file(md_path, ctype, path_tmpl, directory)
                if page and page["url"] not in seen_paths:
                    seen_paths.add(page["url"])
                    pages.append(page)
        return pages

    def _read_file(self, md_path: Path, ctype: str, path_tmpl: str, base_dir: Path) -> dict | None:
        text = md_path.read_text(encoding="utf-8").lstrip("﻿")
        frontmatter, body = _split_frontmatter(text)

        # slug: explicit frontmatter slug wins; else the path relative to the
        # collection dir without extension (so nested dirs become nested routes).
        rel = md_path.relative_to(base_dir).with_suffix("")
        slug = str(frontmatter.get("slug") or rel).replace("\\", "/")

        route = path_tmpl.format(slug=slug)
        url = f"{self.base_url}{route}" if self.base_url else route

        content = normalize_content(frontmatter, ctype, body=body)
        title = content.get("title") or _title_from_slug(rel.name)
        content.setdefault("title", title)

        return {
            "url": url,
            "title": title,
            "type": ctype,
            "content": content,
            "source_path": str(md_path),
        }


# --------------------------------------------------------------------------
# Frontmatter parsing (YAML if available; a small tolerant fallback if not)
# --------------------------------------------------------------------------
def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Files with no `---` block yield ({}, text)."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text
    # Find the closing delimiter after the opening one.
    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:]).strip()
    return _parse_yaml(fm_text), body


def _parse_yaml(fm_text: str) -> dict:
    try:
        import yaml
    except ImportError:
        return _parse_simple(fm_text)
    try:
        data = yaml.safe_load(fm_text)
    except Exception:  # noqa: BLE001
        return _parse_simple(fm_text)
    return data if isinstance(data, dict) else {}


def _parse_simple(fm_text: str) -> dict:
    """
    Minimal `key: value` frontmatter parser used only when PyYAML isn't installed.
    Handles scalars, `true/false`, inline `[a, b]` lists, and `- item` block lists.
    """
    out: dict = {}
    current_key = None
    for raw in fm_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- ") and current_key is not None:
            out.setdefault(current_key, [])
            if isinstance(out[current_key], list):
                out[current_key].append(_coerce(raw.lstrip()[2:].strip()))
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            out[key] = []          # a block list (or empty) may follow
            current_key = key
        else:
            out[key] = _coerce(value)
            current_key = key
    # Drop keys that stayed empty lists but never got items and weren't meant to be lists.
    return {k: v for k, v in out.items() if v != []}


def _coerce(value: str):
    v = value.strip().strip('"').strip("'")
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [s.strip().strip('"').strip("'") for s in inner.split(",")] if inner else []
    return v


def _title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()
