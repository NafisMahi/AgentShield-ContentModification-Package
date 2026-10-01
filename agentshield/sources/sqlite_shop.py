"""Content source: a SQLite database of products and articles.

Content lives in SQL tables rather than files. `load()` runs one query per table
and maps the columns through `normalize_content`; the rest of the pipeline is
unchanged. To target MySQL or Postgres, replace `sqlite3.connect(...)` with
`pymysql.connect(...)` or `psycopg2.connect(...)`; the mapping code is the same.

Expected schema:
    products(slug, name, description, price_cents, sale_price_cents, stock, sku, category)
    articles(slug, title, body, author, published_at, tags)

Configuration (agentshield.config.json -> "source"):

    "source": {
      "type": "sqlite_shop",
      "db": "demo-db-site/data/shop.sqlite",   # path to the .sqlite file
      "baseUrl": "",                            # optional route prefix
      "productPath": "/product/{slug}",
      "articlePath": "/article/{slug}"
    }
"""
from __future__ import annotations

import sqlite3

from .base import normalize_content


def _money(cents):
    """Integer cents -> a '$x.xx' string; None/empty -> None (so normalize skips it)."""
    if cents in (None, ""):
        return None
    return f"${int(cents) / 100:.2f}"


class SqliteShopSource:
    def __init__(self, source_cfg: dict):
        self.db = source_cfg.get("db") or source_cfg.get("root")
        if not self.db:
            raise ValueError("sqlite_shop source needs a 'db' path in the config.")
        self.base = (source_cfg.get("baseUrl") or "").rstrip("/")
        self.product_path = source_cfg.get("productPath", "/product/{slug}")
        self.article_path = source_cfg.get("articlePath", "/article/{slug}")

    def load(self) -> list[dict]:
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        try:
            return self._products(con) + self._articles(con)
        finally:
            con.close()

    def _products(self, con):
        pages = []
        for row in con.execute(
            "SELECT slug, name, description, price_cents, sale_price_cents, "
            "stock, sku, category FROM products ORDER BY slug"):
            on_sale = bool(row["sale_price_cents"])
            fields = {
                "title":         row["name"],
                "description":   row["description"],
                "price":         _money(row["sale_price_cents"] if on_sale else row["price_cents"]),
                "regular_price": _money(row["price_cents"]) if on_sale else None,
                "sku":           row["sku"],
                "availability":  row["stock"] > 0,
                "category":      row["category"],
            }
            pages.append(self._page(row["slug"], row["name"], "product", fields, self.product_path))
        return pages

    def _articles(self, con):
        pages = []
        for row in con.execute(
            "SELECT slug, title, body, author, published_at, tags FROM articles ORDER BY slug"):
            fields = {
                "title":       row["title"],
                "description": row["body"],
                "author":      row["author"],
                "date":        row["published_at"],
                "tags":        row["tags"],
            }
            pages.append(self._page(row["slug"], row["title"], "article", fields, self.article_path))
        return pages

    def _page(self, slug, title, ctype, fields, path_tmpl):
        route = f"{self.base}{path_tmpl.format(slug=slug)}"
        return {
            "url": route,
            "title": title,
            "type": ctype,
            "content": normalize_content(fields, ctype),
            "source_path": f"{self.db}#{ctype}/{slug}",
        }
