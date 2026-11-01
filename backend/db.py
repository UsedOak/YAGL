"""SQLite-backed storage for a single shared YAGL instance."""
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("YAGL_DB_PATH", "/data/yagl.sqlite3"))

SEED_CATEGORIES = {
    "Dry Pasta": ["pasta", "spaghetti", "linguine", "penne", "macaroni", "noodles"],
    "Canned Foods": ["canned", "spaghettios", "beans", "soup", "ravioli"],
    "Boxed Meals": ["mac & cheese", "mac and cheese", "hamburger helper", "boxed dinner"],
    "Rice & Grains": ["rice", "quinoa", "oats"],
    "Breakfast & Cereal": ["cereal", "oatmeal", "pancake", "syrup", "waffles"],
    "Bread & Bakery": ["bread", "bagels", "buns", "tortillas"],
    "Snacks": ["chips", "crackers", "cookies", "pretzels", "popcorn"],
    "Beverages": ["soda", "juice", "coffee", "tea", "water"],
    "Dairy & Eggs": ["milk", "cheese", "yogurt", "butter", "eggs"],
    "Meat & Seafood": ["chicken", "beef", "turkey", "fish", "bacon"],
    "Produce": ["apples", "bananas", "lettuce", "tomatoes", "potatoes"],
    "Frozen Foods": ["frozen", "ice cream", "pizza", "popsicles"],
    "Paper Goods": ["paper towels", "toilet paper", "napkins", "tissues"],
    "Cleaning Supplies": ["detergent", "dish soap", "bleach", "cleaner"],
    "Personal Care": ["shampoo", "toothpaste", "deodorant", "soap"],
    "Pet Supplies": ["cat food", "dog food", "cat litter"],
}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    db.execute("PRAGMA journal_mode = WAL")
    return db


@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with transaction() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
          keywords TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS catalog (
          name TEXT PRIMARY KEY COLLATE NOCASE,
          category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
          category_locked INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 1 AND quantity <= 9999),
          checked INTEGER NOT NULL DEFAULT 0 CHECK(checked IN (0, 1)),
          category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
          category_locked INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS stores (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          location TEXT NOT NULL DEFAULT '', store_code TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS aisles (
          id INTEGER PRIMARY KEY,
          store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
          code TEXT NOT NULL COLLATE NOCASE, description TEXT NOT NULL DEFAULT '',
          sort_order INTEGER NOT NULL DEFAULT 0,
          UNIQUE (store_id, code)
        );
        CREATE TABLE IF NOT EXISTS category_locations (
          store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
          category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
          aisle_id INTEGER NOT NULL REFERENCES aisles(id) ON DELETE CASCADE,
          PRIMARY KEY (store_id, category_id)
        );
        CREATE TABLE IF NOT EXISTS product_locations (
          store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
          product_name TEXT NOT NULL COLLATE NOCASE,
          aisle_id INTEGER NOT NULL REFERENCES aisles(id) ON DELETE CASCADE,
          PRIMARY KEY (store_id, product_name)
        );
        CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at, id);
        CREATE INDEX IF NOT EXISTS idx_aisles_order ON aisles(store_id, sort_order);
        """)
        # Forward-compatible with early development SQLite files.
        for table in ("catalog", "items"):
            columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            if "category_locked" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN category_locked INTEGER NOT NULL DEFAULT 0")
        if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            db.executemany("INSERT INTO categories(name, keywords) VALUES (?, ?)",
                           [(name, json.dumps(words)) for name, words in SEED_CATEGORIES.items()])


def rows(db, query, args=()):
    return [dict(row) for row in db.execute(query, args)]


def parse_keywords(value):
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise ValueError("Keywords must be a list or comma-separated text")
    return list(dict.fromkeys([str(x).strip().lower() for x in value if str(x).strip()]))[:60]


def infer_category(db, name):
    known = db.execute("SELECT category_id, category_locked FROM catalog WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if known and (known["category_locked"] or known["category_id"] is not None):
        return known["category_id"]
    normalized = name.casefold()
    possibilities = []
    for cat in db.execute("SELECT id, name, keywords FROM categories"):
        words = [cat["name"].casefold()] + json.loads(cat["keywords"])
        for word in words:
            if word and re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", normalized):
                possibilities.append((len(word), cat["id"]))
    return max(possibilities)[1] if possibilities else None


def store_layout(db, store_id):
    store = db.execute("SELECT * FROM stores WHERE id=?", (store_id,)).fetchone()
    if not store:
        return None
    return {
        "store": dict(store),
        "aisles": rows(db, "SELECT * FROM aisles WHERE store_id=? ORDER BY sort_order, id", (store_id,)),
        "category_locations": rows(db, "SELECT cl.category_id, c.name category_name, cl.aisle_id FROM category_locations cl JOIN categories c ON c.id=cl.category_id WHERE cl.store_id=? ORDER BY c.name", (store_id,)),
        "product_locations": rows(db, "SELECT product_name, aisle_id FROM product_locations WHERE store_id=? ORDER BY product_name", (store_id,)),
    }


def state(store_id=None):
    db = connect()
    try:
        store_id = int(store_id) if store_id and str(store_id).isdigit() else None
        stores = rows(db, "SELECT * FROM stores ORDER BY name COLLATE NOCASE, id")
        categories = rows(db, "SELECT * FROM categories ORDER BY name COLLATE NOCASE")
        for c in categories:
            c["keywords"] = json.loads(c["keywords"])
        items = rows(db, """SELECT i.*, c.name AS category_name FROM items i
                     LEFT JOIN categories c ON c.id=i.category_id ORDER BY i.id""")
        # Previously unmapped items can learn from categories/keywords added later.
        category_names = {c["id"]: c["name"] for c in categories}
        for item in items:
            if item["category_id"] is None and not item["category_locked"]:
                inferred = infer_category(db, item["name"])
                if inferred is not None:
                    item["category_id"] = inferred
                    item["category_name"] = category_names.get(inferred)
        layout = store_layout(db, store_id) if store_id else None
        if layout:
            aisles = {a["id"]: a for a in layout["aisles"]}
            catmap = {m["category_id"]: m["aisle_id"] for m in layout["category_locations"]}
            prodmap = {m["product_name"].casefold(): m["aisle_id"] for m in layout["product_locations"]}
            for item in items:
                aisle_id = prodmap.get(item["name"].casefold())
                source = "product" if aisle_id is not None else None
                if aisle_id is None and item["category_id"] in catmap:
                    aisle_id = catmap[item["category_id"]]
                    source = "category"
                aisle = aisles.get(aisle_id)
                item.update(aisle_id=aisle_id, aisle_code=aisle["code"] if aisle else None,
                            aisle_description=aisle["description"] if aisle else None,
                            aisle_order=aisle["sort_order"] if aisle else None,
                            location_source=source)
            items.sort(key=lambda x: (x["aisle_order"] is None,
                                      x["aisle_order"] if x["aisle_order"] is not None else 0,
                                      x["aisle_id"] or 0, x["id"]))
        return {"items": items, "stores": stores, "categories": categories, "layout": layout,
                "version": "0.1.0-rc1"}
    finally:
        db.close()
