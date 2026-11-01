"""YAGL HTTP/WebSocket API. Single-process application by design."""
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .db import connect, init_db, infer_category, parse_keywords, rows, state, store_layout, transaction

VERSION = "0.1.0-rc1"
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="YAGL", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")
clients = set()
client_send_lock = asyncio.Lock()


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def name_field(data, field="name", maxlen=120):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maxlen:
        fail(f"{field} must contain 1–{maxlen} characters")
    return value.strip()


def text_field(data, field, maxlen=240):
    value = data.get(field, "")
    if not isinstance(value, str) or len(value.strip()) > maxlen:
        fail(f"{field} must be text up to {maxlen} characters")
    return value.strip()


def positive_int(value, field="id", minimum=1, maximum=999999999):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(f"{field} must be an integer between {minimum} and {maximum}")
    return value


def exists(db, table, identifier):
    # Table names are only called with internal string constants.
    if not db.execute(f"SELECT 1 FROM {table} WHERE id=?", (identifier,)).fetchone():
        fail(f"{table[:-1].capitalize()} not found", 404)


def belongs_aisle(db, store_id, aisle_id):
    if aisle_id is None:
        return
    positive_int(aisle_id, "aisle_id")
    if not db.execute("SELECT 1 FROM aisles WHERE id=? AND store_id=?", (aisle_id, store_id)).fetchone():
        fail("Aisle does not belong to this store")


async def changed():
    async with client_send_lock:
        for ws in list(clients):
            try:
                await ws.send_json({"type": "changed"})
            except Exception:
                clients.discard(ws)


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "A record with this name already exists, or it is in use."})


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.websocket("/api/live")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)


@app.get("/api/state")
def get_state(store_id: int | None = None):
    return state(store_id)


@app.post("/api/items", status_code=201)
async def add_item(data: dict = Body(...)):
    name = name_field(data)
    quantity = positive_int(data.get("quantity", 1), "quantity", maximum=9999)
    with transaction() as db:
        duplicate = db.execute("SELECT id, quantity FROM items WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        if duplicate:
            return JSONResponse(status_code=409, content={"detail": "This item is already on the list", "existing_id": duplicate["id"], "quantity": duplicate["quantity"]})
        category_id = infer_category(db, name)
        cursor = db.execute("INSERT INTO items(name, quantity, category_id) VALUES (?, ?, ?)", (name, quantity, category_id))
        db.execute("INSERT OR IGNORE INTO catalog(name, category_id) VALUES (?, ?)", (name, category_id))
        result = {"id": cursor.lastrowid}
    await changed()
    return result


@app.patch("/api/items/{item_id}")
async def patch_item(item_id: int, data: dict = Body(...)):
    allowed = {"name", "quantity", "checked", "category_id"}
    if not data or not set(data).issubset(allowed):
        fail("Provide item fields: name, quantity, checked, category_id")
    with transaction() as db:
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            fail("Item not found", 404)
        fields = dict(item)
        if "name" in data:
            fields["name"] = name_field(data)
            duplicate = db.execute("SELECT id FROM items WHERE name=? COLLATE NOCASE AND id<>?", (fields["name"], item_id)).fetchone()
            if duplicate:
                fail("Another item with that name is already on the list", 409)
        if "quantity" in data:
            fields["quantity"] = positive_int(data["quantity"], "quantity", maximum=9999)
        if "checked" in data:
            if type(data["checked"]) is not bool:
                fail("checked must be true or false")
            fields["checked"] = int(data["checked"])
        if "category_id" in data:
            fields["category_locked"] = 1
            value = data["category_id"]
            if value is not None:
                positive_int(value, "category_id")
                exists(db, "categories", value)
            fields["category_id"] = value
        db.execute("UPDATE items SET name=?, quantity=?, checked=?, category_id=?, category_locked=? WHERE id=?",
                   (fields["name"], fields["quantity"], fields["checked"], fields["category_id"], fields["category_locked"], item_id))
        if "name" in data or "category_id" in data:
            db.execute("INSERT INTO catalog(name,category_id,category_locked) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET category_id=excluded.category_id, category_locked=excluded.category_locked",
                       (fields["name"], fields["category_id"], fields["category_locked"]))
    await changed()
    return {"ok": True}


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int):
    with transaction() as db:
        if db.execute("DELETE FROM items WHERE id=?", (item_id,)).rowcount == 0:
            fail("Item not found", 404)
    await changed()
    return {"ok": True}


@app.post("/api/items/clear-completed")
async def clear_completed():
    with transaction() as db:
        count = db.execute("DELETE FROM items WHERE checked=1").rowcount
    if count:
        await changed()
    return {"removed": count}


@app.post("/api/categories", status_code=201)
async def create_category(data: dict = Body(...)):
    name = name_field(data)
    try:
        keywords = parse_keywords(data.get("keywords", []))
    except ValueError as e:
        fail(str(e))
    with transaction() as db:
        cursor = db.execute("INSERT INTO categories(name,keywords) VALUES (?,?)", (name, json.dumps(keywords)))
        result = {"id": cursor.lastrowid}
    await changed()
    return result


@app.patch("/api/categories/{category_id}")
async def update_category(category_id: int, data: dict = Body(...)):
    with transaction() as db:
        exists(db, "categories", category_id)
        row = db.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
        name = name_field(data) if "name" in data else row["name"]
        try:
            keywords = parse_keywords(data["keywords"]) if "keywords" in data else json.loads(row["keywords"])
        except ValueError as e:
            fail(str(e))
        db.execute("UPDATE categories SET name=?, keywords=? WHERE id=?", (name, json.dumps(keywords), category_id))
    await changed()
    return {"ok": True}


@app.delete("/api/categories/{category_id}")
async def delete_category(category_id: int):
    with transaction() as db:
        if not db.execute("DELETE FROM categories WHERE id=?", (category_id,)).rowcount:
            fail("Category not found", 404)
    await changed()
    return {"ok": True}


@app.post("/api/stores", status_code=201)
async def create_store(data: dict = Body(...)):
    name = name_field(data)
    location = text_field(data, "location")
    store_code = text_field(data, "store_code", 60)
    with transaction() as db:
        cursor = db.execute("INSERT INTO stores(name,location,store_code) VALUES (?,?,?)", (name, location, store_code))
        result = {"id": cursor.lastrowid}
    await changed()
    return result


@app.patch("/api/stores/{store_id}")
async def update_store(store_id: int, data: dict = Body(...)):
    with transaction() as db:
        exists(db, "stores", store_id)
        row = db.execute("SELECT * FROM stores WHERE id=?", (store_id,)).fetchone()
        db.execute("UPDATE stores SET name=?, location=?, store_code=? WHERE id=?", (
            name_field(data) if "name" in data else row["name"],
            text_field(data, "location") if "location" in data else row["location"],
            text_field(data, "store_code", 60) if "store_code" in data else row["store_code"], store_id))
    await changed()
    return {"ok": True}


@app.delete("/api/stores/{store_id}")
async def delete_store(store_id: int):
    with transaction() as db:
        if not db.execute("DELETE FROM stores WHERE id=?", (store_id,)).rowcount:
            fail("Store not found", 404)
    await changed()
    return {"ok": True}


@app.post("/api/stores/{store_id}/aisles", status_code=201)
async def add_aisle(store_id: int, data: dict = Body(...)):
    code = name_field(data, "code", 50)
    description = text_field(data, "description", 120)
    with transaction() as db:
        exists(db, "stores", store_id)
        index = db.execute("SELECT COALESCE(MAX(sort_order), -1)+1 FROM aisles WHERE store_id=?", (store_id,)).fetchone()[0]
        cursor = db.execute("INSERT INTO aisles(store_id,code,description,sort_order) VALUES (?,?,?,?)",
                            (store_id, code, description, index))
        result = {"id": cursor.lastrowid}
    await changed()
    return result


@app.patch("/api/stores/{store_id}/aisles/{aisle_id}")
async def update_aisle(store_id: int, aisle_id: int, data: dict = Body(...)):
    with transaction() as db:
        belongs_aisle(db, store_id, aisle_id)
        row = db.execute("SELECT * FROM aisles WHERE id=?", (aisle_id,)).fetchone()
        db.execute("UPDATE aisles SET code=?, description=? WHERE id=?", (
            name_field(data, "code", 50) if "code" in data else row["code"],
            text_field(data, "description", 120) if "description" in data else row["description"], aisle_id))
    await changed()
    return {"ok": True}


@app.delete("/api/stores/{store_id}/aisles/{aisle_id}")
async def remove_aisle(store_id: int, aisle_id: int):
    with transaction() as db:
        belongs_aisle(db, store_id, aisle_id)
        db.execute("DELETE FROM aisles WHERE id=?", (aisle_id,))
    await changed()
    return {"ok": True}


@app.put("/api/stores/{store_id}/aisles/order")
async def reorder_aisles(store_id: int, data: dict = Body(...)):
    ids = data.get("ids")
    if not isinstance(ids, list) or any(type(x) is not int for x in ids) or len(ids) != len(set(ids)):
        fail("ids must be a unique list of aisle IDs")
    with transaction() as db:
        exists(db, "stores", store_id)
        actual = {row[0] for row in db.execute("SELECT id FROM aisles WHERE store_id=?", (store_id,))}
        if set(ids) != actual:
            fail("The order must contain each aisle from this store exactly once")
        db.executemany("UPDATE aisles SET sort_order=? WHERE id=?", [(i, aid) for i, aid in enumerate(ids)])
    await changed()
    return {"ok": True}


@app.put("/api/stores/{store_id}/categories/{category_id}")
async def map_category(store_id: int, category_id: int, data: dict = Body(...)):
    aisle_id = data.get("aisle_id")
    with transaction() as db:
        exists(db, "stores", store_id)
        exists(db, "categories", category_id)
        if aisle_id is None:
            db.execute("DELETE FROM category_locations WHERE store_id=? AND category_id=?", (store_id, category_id))
        else:
            belongs_aisle(db, store_id, aisle_id)
            db.execute("INSERT INTO category_locations(store_id,category_id,aisle_id) VALUES (?,?,?) ON CONFLICT(store_id,category_id) DO UPDATE SET aisle_id=excluded.aisle_id", (store_id, category_id, aisle_id))
    await changed()
    return {"ok": True}


@app.put("/api/stores/{store_id}/products")
async def map_product(store_id: int, data: dict = Body(...)):
    product = name_field(data, "product_name")
    aisle_id = data.get("aisle_id")
    with transaction() as db:
        exists(db, "stores", store_id)
        if aisle_id is None:
            db.execute("DELETE FROM product_locations WHERE store_id=? AND product_name=? COLLATE NOCASE", (store_id, product))
        else:
            belongs_aisle(db, store_id, aisle_id)
            db.execute("INSERT INTO product_locations(store_id,product_name,aisle_id) VALUES (?,?,?) ON CONFLICT(store_id,product_name) DO UPDATE SET aisle_id=excluded.aisle_id", (store_id, product, aisle_id))
    await changed()
    return {"ok": True}


def export_object(db, store_id):
    layout = store_layout(db, store_id)
    if layout is None:
        fail("Store not found", 404)
    aisle_codes = {a["id"]: a["code"] for a in layout["aisles"]}
    mapped_categories = {x["category_id"] for x in layout["category_locations"]}
    return {
        "format": "yagl-store-layout", "schema_version": 1,
        "store": {k: layout["store"][k] for k in ("name", "location", "store_code")},
        "aisles": [{k: a[k] for k in ("code", "description", "sort_order")} for a in layout["aisles"]],
        "category_locations": [
            {"category": x["category_name"], "keywords": json.loads(db.execute("SELECT keywords FROM categories WHERE id=?", (x["category_id"],)).fetchone()[0]),
             "aisle": aisle_codes[x["aisle_id"]]} for x in layout["category_locations"]
        ],
        "product_locations": [{"product": x["product_name"], "aisle": aisle_codes[x["aisle_id"]]} for x in layout["product_locations"]],
        "product_categories": [
            {"product": x["name"], "category": x["category_name"]} for x in rows(db, """SELECT p.name, c.name category_name FROM catalog p JOIN categories c ON c.id=p.category_id ORDER BY p.name""")
            if db.execute("SELECT id FROM categories WHERE name=?", (x["category_name"],)).fetchone()[0] in mapped_categories
        ],
    }


@app.get("/api/stores/{store_id}/export")
def export_store(store_id: int):
    db = connect()
    try:
        payload = export_object(db, store_id)
    finally:
        db.close()
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return Response(content, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="yagl-store-{store_id}.json"'})


def validated_import(payload):
    if not isinstance(payload, dict) or payload.get("format") != "yagl-store-layout" or payload.get("schema_version") != 1:
        fail("Not a supported YAGL store layout (schema version 1 required)")
    for key in ("store", "aisles", "category_locations", "product_locations", "product_categories"):
        if key not in payload:
            fail(f"Missing required import section: {key}")
    store = payload["store"]
    if not isinstance(store, dict):
        fail("Invalid store information")
    name_field(store)
    for key in ("location", "store_code"):
        text_field(store, key)
    for field in ("aisles", "category_locations", "product_locations", "product_categories"):
        if not isinstance(payload[field], list) or len(payload[field]) > 1500:
            fail(f"Invalid or oversized {field} section")
    codes = set()
    for aisle in payload["aisles"]:
        if not isinstance(aisle, dict):
            fail("Invalid aisle")
        code = name_field(aisle, "code", 50).casefold()
        text_field(aisle, "description", 120)
        positive_int(aisle.get("sort_order"), "sort_order", minimum=0, maximum=100000)
        if code in codes:
            fail("Duplicate aisle codes in import")
        codes.add(code)
    for record in payload["category_locations"]:
        if not isinstance(record, dict):
            fail("Invalid category mapping")
        name_field(record, "category")
        try: parse_keywords(record.get("keywords", []))
        except ValueError as e: fail(str(e))
        if name_field(record, "aisle", 50).casefold() not in codes:
            fail("Category mapping references an unknown aisle")
    for record in payload["product_locations"]:
        if not isinstance(record, dict):
            fail("Invalid product mapping")
        name_field(record, "product")
        if name_field(record, "aisle", 50).casefold() not in codes:
            fail("Product mapping references an unknown aisle")
    for record in payload["product_categories"]:
        if not isinstance(record, dict):
            fail("Invalid product category")
        name_field(record, "product")
        name_field(record, "category")
    return payload


@app.post("/api/stores/{store_id}/import/preview")
def preview_import(store_id: int, data: dict = Body(...)):
    db = connect()
    try:
        if not store_layout(db, store_id):
            fail("Store not found", 404)
        validated_import(data.get("payload"))
    finally:
        db.close()
    payload = data["payload"]
    return {"from_store": payload["store"]["name"], "target_store_id": store_id,
            "aisles": len(payload["aisles"]), "category_locations": len(payload["category_locations"]),
            "product_locations": len(payload["product_locations"]),
            "product_categories": len(payload["product_categories"]),
            "warning": "Export a backup of your current store first. Replace removes its existing aisle and location mappings; Merge preserves existing mappings."}


@app.post("/api/stores/{store_id}/import")
async def import_store(store_id: int, data: dict = Body(...)):
    mode = data.get("mode")
    if mode not in ("merge", "replace"):
        fail("mode must be merge or replace")
    payload = validated_import(data.get("payload"))
    with transaction() as db:
        exists(db, "stores", store_id)
        if mode == "replace":
            db.execute("DELETE FROM aisles WHERE store_id=?", (store_id,))
        lookup = {a["code"].casefold(): a for a in rows(db, "SELECT id,code FROM aisles WHERE store_id=?", (store_id,))}
        for aisle in sorted(payload["aisles"], key=lambda x: x["sort_order"]):
            key = aisle["code"].casefold()
            if key not in lookup:
                # Merge appends new aisles without disrupting pre-existing walking order.
                if mode == "replace":
                    order = aisle["sort_order"]
                else:
                    order = db.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM aisles WHERE store_id=?", (store_id,)).fetchone()[0]
                cur = db.execute("INSERT INTO aisles(store_id,code,description,sort_order) VALUES (?,?,?,?)",
                                 (store_id, aisle["code"], aisle.get("description", ""), order))
                lookup[key] = {"id": cur.lastrowid}
        for record in payload["category_locations"]:
            cname = record["category"]
            cat = db.execute("SELECT id FROM categories WHERE name=? COLLATE NOCASE", (cname,)).fetchone()
            if cat is None:
                cid = db.execute("INSERT INTO categories(name,keywords) VALUES (?,?)", (cname, json.dumps(parse_keywords(record.get("keywords", []))))).lastrowid
            else:
                cid = cat["id"]
            aid = lookup[record["aisle"].casefold()]["id"]
            if mode == "replace":
                db.execute("INSERT OR REPLACE INTO category_locations(store_id,category_id,aisle_id) VALUES (?,?,?)", (store_id, cid, aid))
            else:
                db.execute("INSERT OR IGNORE INTO category_locations(store_id,category_id,aisle_id) VALUES (?,?,?)", (store_id, cid, aid))
        for record in payload["product_locations"]:
            aid = lookup[record["aisle"].casefold()]["id"]
            sql = "INSERT OR REPLACE" if mode == "replace" else "INSERT OR IGNORE"
            db.execute(f"{sql} INTO product_locations(store_id,product_name,aisle_id) VALUES (?,?,?)", (store_id, record["product"], aid))
        for record in payload["product_categories"]:
            cat = db.execute("SELECT id FROM categories WHERE name=? COLLATE NOCASE", (record["category"],)).fetchone()
            if cat:
                db.execute("INSERT OR IGNORE INTO catalog(name,category_id) VALUES (?,?)", (record["product"], cat["id"]))
        # Intentionally does not replace target store identity or modify the active shopping list.
    await changed()
    return {"ok": True, "mode": mode}
