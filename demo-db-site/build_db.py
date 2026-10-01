"""Build the demo SQLite database for the DB-driven site (Tinderbox Coffee).

Run once: `python build_db.py`. Creates data/shop.sqlite with `products` and
`articles` tables. Both the demo site (server.py) and the pipeline (the
sqlite_shop adapter) read this same database.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data" / "shop.sqlite"

PRODUCTS = [
    # slug, name, description, price_cents, sale_price_cents, stock, sku, category
    ("ethiopia-yirgacheffe", "Ethiopia Yirgacheffe",
     "A bright, floral washed coffee from the Yirgacheffe region. Expect notes of "
     "jasmine, bergamot, and lemon, with a clean, tea-like body. Roasted light to keep "
     "its delicate aromatics intact.",
     1800, 1500, 24, "COF-ETH-01", "Single Origin"),
    ("colombia-supremo", "Colombia Supremo",
     "A dependable, well-balanced Colombian with milk-chocolate sweetness, a round body, "
     "and a gentle caramel finish. Roasted medium for everyday drinking.",
     1600, None, 0, "COF-COL-02", "Single Origin"),
    ("house-espresso-blend", "House Espresso Blend",
     "Our signature espresso: a blend built for rich crema and a syrupy body, with cocoa, "
     "toasted hazelnut, and a dried-fruit sweetness that stands up to milk.",
     1400, None, 50, "COF-ESP-03", "Blends"),
]

ARTICLES = [
    # slug, title, body, author, published_at, tags
    ("how-to-brew-pour-over", "How to Brew the Perfect Pour-Over",
     "Pour-over coffee rewards patience and consistency. The method is simple, but small "
     "changes in grind, water temperature, and pour rate make a real difference.\n\n"
     "Start with a medium-fine grind and water just off the boil, around 96C. Bloom the "
     "grounds with twice their weight in water for 30 seconds, then pour in slow, steady "
     "circles. A full brew should finish in about three minutes.",
     "Dana Reyes", "2026-05-10", "brewing, guide"),
    ("light-vs-dark-roast", "Light vs Dark Roast: What Actually Changes",
     "Roast level is the single biggest lever a roaster pulls, and it changes far more than "
     "colour. Lighter roasts preserve the bean's origin character and acidity; darker roasts "
     "trade that for body and bittersweet, roast-driven flavour.\n\n"
     "Contrary to a common belief, darker roasts do not contain meaningfully more caffeine. "
     "By weight the difference is negligible; roast level mostly changes taste, not strength.",
     "Sam Okafor", "2026-04-22", "roasting"),
]


def main():
    DB.parent.mkdir(exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            slug TEXT UNIQUE, name TEXT, description TEXT,
            price_cents INTEGER, sale_price_cents INTEGER,
            stock INTEGER, sku TEXT, category TEXT
        );
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            slug TEXT UNIQUE, title TEXT, body TEXT,
            author TEXT, published_at TEXT, tags TEXT
        );
        """
    )
    con.executemany(
        "INSERT INTO products (slug,name,description,price_cents,sale_price_cents,stock,sku,category) "
        "VALUES (?,?,?,?,?,?,?,?)", PRODUCTS)
    con.executemany(
        "INSERT INTO articles (slug,title,body,author,published_at,tags) VALUES (?,?,?,?,?,?)", ARTICLES)
    con.commit()
    con.close()
    print(f"Built {DB}  ({len(PRODUCTS)} products, {len(ARTICLES)} articles)")


if __name__ == "__main__":
    main()
