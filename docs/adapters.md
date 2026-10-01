# Writing a source adapter

AgentShield-local reads a site's products and articles through a *source adapter*. Two
adapters ship with the tool:

- `markdown` ([agentshield/sources/markdown.py](../agentshield/sources/markdown.py)): `.md`
  files with YAML frontmatter.
- `sqlite_shop` ([agentshield/sources/sqlite_shop.py](../agentshield/sources/sqlite_shop.py)):
  `products` and `articles` tables in a SQLite database.

To support a different storage system (another database, a JSON export, a CMS API), write a
small adapter. This guide describes the contract and shows how.

## The contract

An adapter is any object with one method:

```python
def load(self) -> list[dict]:
    ...
```

It returns one dict per content page:

```python
{
  "url":     "/product/raw-wildflower-honey",   # the route path the site serves this at
  "title":   "Raw Wildflower Honey",
  "type":    "product",                          # "product" | "article" | "other"
  "content": {                                   # structured fields (see below)
      "type": "product",
      "title": "Raw Wildflower Honey",
      "description": "Unfiltered, cold-extracted honey...",
      "price": "$14.99",
      "availability": "In stock",
      "categories": ["Pantry"]
  },
  "source_path": "content/products/raw-wildflower-honey.md"   # optional
}
```

Two rules matter most:

1. **`url` is the route path.** The injector matches requests by URL path, so `url` must be
   the path the live site serves that page at. `agentshield verify` reports any path that
   does not match.
2. **Populate the product fields you have** (`price`, `shipping`, `availability`, `sku`, and
   so on). Product disinformation falsifies one of these, so more fields give more options.

## Content fields

`content` follows `PageContent` in [agentshield/schemas.py](../agentshield/schemas.py). Fill
only the fields that exist.

| Field | For | Notes |
|---|---|---|
| `type` | all | `product` / `article` / `other` (no prompt is injected into `other` pages) |
| `title`, `description` | all | description is the product description or the article body |
| `price`, `regular_price`, `sale_price`, `shipping`, `sku`, `availability`, `rating`, `categories` | product | the concrete labels an agent would report |
| `summary`, `author`, `date_published`, `tags` | article | |
| `additional_labels` | all | any other labels present on the page |

## normalize_content

You rarely build `content` by hand. `normalize_content()` in
[agentshield/sources/base.py](../agentshield/sources/base.py) takes a loose field dict and
returns a clean `content` dict:

```python
from .base import normalize_content
content = normalize_content(raw_fields, page_type="product", body=body_text)
```

It renames common aliases (`was` to `regular_price`, `short` to `summary`, `date` to
`date_published`, `stock` to `availability`, `category` to `categories`), converts a boolean
`availability` to `"In stock"` / `"Out of stock"`, accepts a string or list for `categories`
and `tags`, uses `body` as the description when none is given, and routes unrecognised keys
to `additional_labels`. Add your own aliases in `FIELD_ALIASES`.

## Adding an adapter

1. Write the class in `agentshield/sources/mysource.py`:

```python
from .base import normalize_content


class MySource:
    def __init__(self, source_cfg: dict):
        self.root = source_cfg.get("root", ".")     # the "source" block of the config

    def load(self) -> list[dict]:
        pages = []
        for record in self._read_content():           # your storage: files, DB, API
            content = normalize_content(record["fields"], record["type"], body=record.get("body"))
            pages.append({
                "url": record["path"],
                "title": content.get("title"),
                "type": record["type"],
                "content": content,
            })
        return pages
```

2. Register it in [agentshield/sources/base.py](../agentshield/sources/base.py). Import
   inside the factory so an optional dependency loads only when the source is used:

```python
def _mysource_factory(source_cfg):
    from .mysource import MySource
    return MySource(source_cfg)

SOURCES = {
    "markdown": _markdown_factory,
    "sqlite_shop": _sqlite_shop_factory,
    "mysource": _mysource_factory,
}
```

3. Point the config at it:

```json
"source": { "type": "mysource", "root": "/path/to/site" }
```

The rest of the pipeline (`extract`, `configure`, `generate`, `export`, `verify`) is
unchanged.

## Examples

### JSON catalog

```python
import json
from pathlib import Path
from .base import normalize_content


class JsonSource:
    def __init__(self, cfg):
        self.file = Path(cfg["root"]) / cfg.get("file", "catalog.json")

    def load(self):
        data = json.loads(self.file.read_text(encoding="utf-8"))
        return [
            {"url": f"/product/{item['slug']}", "title": item.get("title"),
             "type": "product", "content": normalize_content(item, "product")}
            for item in data["products"]
        ]
```

### Database

If your database already has tables `products(slug, name, description, price_cents,
sale_price_cents, stock, sku, category)` and `articles(slug, title, body, author,
published_at, tags)`, the built-in `sqlite_shop` adapter works with config only:

```json
"source": {
  "type": "sqlite_shop",
  "db": "path/to/shop.sqlite",
  "productPath": "/product/{slug}",
  "articlePath": "/article/{slug}"
}
```

For a different schema, or for MySQL/Postgres, write an adapter. Copy
[sqlite_shop.py](../agentshield/sources/sqlite_shop.py) as the template, change the `SELECT`
statements to your tables, and map your columns in the `fields` dict; `normalize_content` does
the field conversion. For MySQL or Postgres, swap the driver (`pymysql` or `psycopg2`, install
with pip) and use `%s` placeholders. A minimal MySQL adapter:

```python
import pymysql
from .base import normalize_content


class MySiteSource:
    def __init__(self, cfg):
        self.host = cfg["host"]; self.user = cfg["user"]
        self.password = cfg.get("password", ""); self.database = cfg["database"]

    def load(self):
        con = pymysql.connect(host=self.host, user=self.user, password=self.password,
                              database=self.database, cursorclass=pymysql.cursors.DictCursor)
        pages = []
        with con.cursor() as cur:
            cur.execute("SELECT handle, title, body_html, price, in_stock FROM products")
            for row in cur.fetchall():
                fields = {"title": row["title"], "description": row["body_html"],
                          "price": row["price"], "availability": bool(row["in_stock"])}
                pages.append({"url": f"/product/{row['handle']}", "title": row["title"],
                              "type": "product", "content": normalize_content(fields, "product")})
            cur.execute("SELECT handle, title, body_html, author FROM posts")
            for row in cur.fetchall():
                fields = {"title": row["title"], "description": row["body_html"], "author": row["author"]}
                pages.append({"url": f"/blog/{row['handle']}", "title": row["title"],
                              "type": "article", "content": normalize_content(fields, "article")})
        con.close()
        return pages
```

Register it in `base.py` and point the config at it (as in "Adding an adapter"):

```json
"source": { "type": "mysite", "host": "127.0.0.1", "user": "readonly",
            "password": "...", "database": "shop" }
```

The two things you change per site are the `SELECT` statements (your tables and columns) and
the `fields` dict (your columns mapped to the field names above). The `url` must be the path
your site serves each row at.

### CMS or API

Headless CMS platforms (Contentful, Sanity, Strapi, Ghost, and others) serve content over an
HTTP API. The adapter calls the API and maps each item. Use `urllib` (standard library) or
`requests`. If the API returns each item's own URL, use it directly so route matching is
exact; otherwise build the path from a slug field.

```python
import json, urllib.request
from .base import normalize_content


class CmsSource:
    def __init__(self, cfg):
        self.endpoint = cfg["endpoint"]          # e.g. https://cms.example.com/api/products
        self.token = cfg.get("token")
        self.per_page = int(cfg.get("perPage", 100))

    def _get(self, page):
        url = f"{self.endpoint}?page={page}&per_page={self.per_page}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def load(self):
        pages, page = [], 1
        while True:
            items = self._get(page)
            if not items:
                break
            for item in items:
                fields = {"title": item["name"], "description": item["description"],
                          "price": item.get("price"), "availability": item.get("stock_status"),
                          "categories": [c["name"] for c in item.get("categories", [])]}
                pages.append({"url": item.get("url") or f"/product/{item['slug']}",
                              "title": item["name"], "type": "product",
                              "content": normalize_content(fields, "product")})
            if len(items) < self.per_page:
                break
            page += 1
        return pages
```

Register and configure it like any other adapter:

```json
"source": { "type": "cms", "endpoint": "https://cms.example.com/api/products", "token": "..." }
```

Use HTTPS, respect the API's authentication and rate limits, and page through results until a
short or empty page. For a self-hosted CMS whose database you can query directly (for example
WordPress on MySQL), a database adapter is often simpler than the API; see "Database" above.

## Testing an adapter

Load it directly, without the CLI:

```python
import json
from agentshield import config as cfg_mod
from agentshield.sources import get_source

cfg = json.loads(json.dumps(cfg_mod.CONFIG_TEMPLATE))
cfg["source"] = {"type": "mysource", "root": "/path/to/site"}
for page in get_source(cfg).load():
    print(page["type"], page["url"], page["content"].get("title"))
```

Then run `agentshield add --dry` and `agentshield extract --dry` to print the routes and
fields the adapter produced, and `agentshield verify <site-url>` to confirm the routes match
the live site.
