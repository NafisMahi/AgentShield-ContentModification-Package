"""Tinderbox Coffee: a database-driven demo site.

Renders product/article pages from data/shop.sqlite on each request. This is the
same database the pipeline reads through the sqlite_shop adapter. Uses only the
Python standard library (http.server + sqlite3).

    python build_db.py     # once, to create the database
    python server.py       # serves http://localhost:8200
"""
import html
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

DB = Path(__file__).parent / "data" / "shop.sqlite"
PORT = 8200


def _con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def esc(s):
    return html.escape("" if s is None else str(s))


def layout(title, body):
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{esc(title)} &mdash; Tinderbox Coffee</title><style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;"
        "margin:0 auto;padding:24px;color:#241f1b;background:#faf7f3;line-height:1.6}"
        "a{color:#9a5b25;text-decoration:none}a:hover{text-decoration:underline}"
        ".price{font-size:24px;font-weight:700;color:#9a5b25}.was{color:#a08f82;text-decoration:line-through;margin-left:10px}"
        ".muted{color:#7c7169}nav a{margin-right:16px;font-weight:600}h1{margin:.2em 0}"
        "</style></head><body>"
        "<nav><a href=\"/\">Tinderbox Coffee</a><a href=\"/shop\">Shop</a><a href=\"/blog\">Journal</a></nav><hr>"
        f"{body}</body></html>"
    )


def product_page(slug):
    con = _con()
    p = con.execute("SELECT * FROM products WHERE slug=?", (slug,)).fetchone()
    con.close()
    if not p:
        return None
    on_sale = bool(p["sale_price_cents"])
    price = (p["sale_price_cents"] if on_sale else p["price_cents"]) / 100
    was = f"<span class=\"was\">${p['price_cents']/100:.2f}</span>" if on_sale else ""
    stock = "In stock" if p["stock"] > 0 else "Out of stock"
    body = (
        f"<p class=\"muted\">{esc(p['category'])} &middot; SKU {esc(p['sku'])}</p>"
        f"<h1>{esc(p['name'])}</h1>"
        f"<p><span class=\"price\">${price:.2f}</span>{was}</p>"
        f"<p class=\"muted\">{stock} &middot; Free shipping over $35</p>"
        f"<p>{esc(p['description'])}</p>"
        f"<button>Add to cart</button>"
    )
    return layout(p["name"], body)


def article_page(slug):
    con = _con()
    a = con.execute("SELECT * FROM articles WHERE slug=?", (slug,)).fetchone()
    con.close()
    if not a:
        return None
    paras = "".join(f"<p>{esc(x.strip())}</p>" for x in a["body"].split("\n\n") if x.strip())
    body = (
        f"<h1>{esc(a['title'])}</h1>"
        f"<p class=\"muted\">{esc(a['published_at'])} &middot; by {esc(a['author'])} &middot; {esc(a['tags'])}</p>"
        f"{paras}"
    )
    return layout(a["title"], body)


def shop_page():
    con = _con()
    rows = con.execute("SELECT * FROM products ORDER BY slug").fetchall()
    con.close()
    items = "".join(
        f"<li><a href=\"/product/{r['slug']}\">{esc(r['name'])}</a> "
        f"&mdash; ${(r['sale_price_cents'] or r['price_cents'])/100:.2f}</li>" for r in rows)
    return layout("Shop", f"<h1>Shop</h1><ul>{items}</ul>")


def blog_page():
    con = _con()
    rows = con.execute("SELECT * FROM articles ORDER BY slug").fetchall()
    con.close()
    items = "".join(
        f"<li><a href=\"/article/{r['slug']}\">{esc(r['title'])}</a> "
        f"&mdash; {esc(r['author'])}</li>" for r in rows)
    return layout("Journal", f"<h1>The Journal</h1><ul>{items}</ul>")


def home():
    return layout("Home",
                  "<h1>Tinderbox Coffee Roasters</h1>"
                  "<p>A small-batch, <strong>database-driven</strong> demo store. "
                  "Every page is rendered live from SQLite.</p>"
                  "<p><a href=\"/shop\">Shop</a> &middot; <a href=\"/blog\">Journal</a></p>")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        path = path[:-1] if len(path) > 1 and path.endswith("/") else path
        page = None
        if path == "/":
            page = home()
        elif path == "/shop":
            page = shop_page()
        elif path == "/blog":
            page = blog_page()
        elif path.startswith("/product/"):
            page = product_page(path[len("/product/"):])
        elif path.startswith("/article/"):
            page = article_page(path[len("/article/"):])

        if page is None:
            body = b"<!doctype html><html><body><h1>404</h1></body></html>"
            self.send_response(404)
        else:
            body = page.encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if not DB.exists():
        raise SystemExit("shop.sqlite not found. Run `python build_db.py` first.")
    print(f"[python] Tinderbox (sqlite-driven) on http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
