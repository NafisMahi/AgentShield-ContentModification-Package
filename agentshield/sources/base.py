"""Content-source adapters.

An adapter reads a site's products/articles from the local project and returns
them as a list of page dicts:

    {
      "url":     "/product/raw-wildflower-honey",   # route path the injector matches
      "title":   "Raw Wildflower Honey",
      "type":    "product" | "article" | "other",
      "content": {...fields matching agentshield.schemas.PageContent...},
      "source_path": "...",                          # optional
    }

`content` mirrors PageContent: title and description; product fields (price,
regular_price, sale_price, shipping, sku, availability, rating, categories) or
article fields (summary, author, date_published, tags); plus an additional_labels
dict. Only populate fields that exist.

To support a new source type, add a class with a load() method and register it in
SOURCES. markdown.py is the reference implementation.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ContentSource(Protocol):
    def load(self) -> list[dict]:
        ...


def get_source(cfg: dict):
    source_cfg = cfg.get("source") or {}
    kind = source_cfg.get("type", "markdown")
    factory = SOURCES.get(kind)
    if factory is None:
        raise ValueError(
            f"Unknown source.type '{kind}'. Available: {', '.join(sorted(SOURCES))}."
        )
    return factory(source_cfg)


# Canonical PageContent product/article field names.
PRODUCT_FIELDS = (
    "price", "regular_price", "sale_price", "shipping", "sku", "availability", "rating",
)
ARTICLE_FIELDS = ("summary", "author", "date_published", "tags")

# Field-name aliases mapped to their canonical PageContent field.
FIELD_ALIASES = {
    "was": "regular_price",
    "old_price": "regular_price",
    "list_price": "regular_price",
    "sale": "sale_price",
    "excerpt": "summary",
    "short": "summary",
    "tagline": "summary",
    "subtitle": "summary",
    "date": "date_published",
    "published": "date_published",
    "stock": "availability",
    "in_stock": "availability",
    "instock": "availability",
    "category": "categories",
    "cats": "categories",
    "desc": "description",
    "body": "description",
}


def normalize_content(fields: dict, page_type: str, body: str | None = None) -> dict:
    """Map a loose field dict onto the PageContent shape.

    Known fields and their aliases are placed directly. A boolean `availability`
    becomes 'In stock' or 'Out of stock'. `categories` and `tags` accept a string
    or a list. Unrecognised keys are stringified into additional_labels.
    """
    content: dict = {}
    extra: dict = {}

    for raw_key, value in (fields or {}).items():
        if value in (None, "", [], {}):
            continue
        key = FIELD_ALIASES.get(str(raw_key).lower(), str(raw_key).lower())

        if key == "title":
            content["title"] = str(value)
        elif key == "description":
            content["description"] = str(value)
        elif key in PRODUCT_FIELDS:
            if key == "availability" and isinstance(value, bool):
                content[key] = "In stock" if value else "Out of stock"
            else:
                content[key] = str(value)
        elif key == "categories":
            content["categories"] = _as_list(value)
        elif key == "tags":
            content["tags"] = _as_list(value)
        elif key in ("summary", "author", "date_published"):
            content[key] = str(value)
        else:
            extra[str(raw_key)] = _stringify(value)

    if body and not content.get("description"):
        content["description"] = body.strip()
    if extra:
        content["additional_labels"] = extra
    content.setdefault("type", page_type)
    return content


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _stringify(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


# Source-type name -> factory. Adapters are imported lazily so an optional
# dependency loads only when that source is used.
def _markdown_factory(source_cfg):
    from .markdown import MarkdownSource
    return MarkdownSource(source_cfg)


def _sqlite_shop_factory(source_cfg):
    from .sqlite_shop import SqliteShopSource
    return SqliteShopSource(source_cfg)


SOURCES = {
    "markdown": _markdown_factory,
    "sqlite_shop": _sqlite_shop_factory,
}
