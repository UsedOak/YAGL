# Architecture and developer notes

## Intentional simplicity

YAGL has one Python/FastAPI process (Uvicorn, **one worker**), one local SQLite database, and plain frontend JavaScript/CSS/HTML served by the backend. No third-party SaaS or frontend toolchain. The Compose deployment runs as an unprivileged user in a read-only container, with a named data volume for SQLite.

Backend modules:
- `backend/app.py` — REST endpoints, WebSocket notifications, JSON import/export validation.
- `backend/db.py` — SQLite schema, category inference, store-specific sorting, initial categories.
- `backend/backup.py` — consistent SQLite online backup.

Frontend:
- `frontend/index.html` — HTML structure and modal.
- `frontend/style.css` — mobile and desktop styling.
- `frontend/app.js` — list display, forms, store settings, REST calls, WebSocket resync.

## One list, separate views

The server persists `items` once. Each `GET /api/state?store_id=<id>` joins the server list with aisle/category data for the chosen store; items are sorted by explicit route order. The browser sends its own store ID on each fetch and saves its current choice in `localStorage`. Changing one browser's store does not modify a global 'active store'.

WebSocket `/api/live` sends **change notices**, not divergent copies of state; upon receiving notice, clients fetch a fresh snapshot from the authoritative database. A 30-second visible-page poll and focus/visibility refresh help recover from dropped sockets. There is no offline queue or conflict resolution for disconnected editing. Very close simultaneous quantity changes can overwrite one another in this alpha; this is an identified future improvement.

## Categories

Categories have free-form names and comma-separated keywords; catalog product names remember a selected category. Matching preference: already remembered product category, then longest case-insensitive keyword match. Per-store category location applies only to that store. A per-store product location takes precedence over category location. This is deterministic local keyword logic, not AI or official retailer data.

## Database and operations

SQLite uses `foreign_keys=ON`, WAL mode, per-request connections and `BEGIN IMMEDIATE` for writes. Data is stored in `/data/yagl.sqlite3` and its SQLite WAL files. Back up with `backend.backup` using SQLite's backup API. One Uvicorn worker is intentional: WebSocket connected clients are held in process memory and would not all receive notices across multiple workers. Scaling beyond a single container requires a shared message broker.

## API outline

| Method / path | Purpose |
| --- | --- |
| `GET /health` | Health and version |
| `GET /api/state?store_id=ID` | Shared list with optional store-sorted view |
| `POST /api/items` | Add item, reject same-name duplicate with `409` |
| `PATCH /api/items/ID` | Rename, categorize, change quantity or checked state |
| `DELETE /api/items/ID` | Remove one item |
| `POST /api/items/clear-completed` | Clear checked items only |
| `POST/PATCH/DELETE /api/categories` | Category management (`/ID` for modification) |
| `POST/PATCH/DELETE /api/stores` | Store management (`/ID` for modification) |
| `POST /api/stores/ID/aisles` | Add an aisle/zone |
| `PATCH/DELETE /api/stores/ID/aisles/AISLE_ID` | Edit/remove aisle |
| `PUT /api/stores/ID/aisles/order` | Supply exact array of aisle IDs in desired order |
| `PUT /api/stores/ID/categories/CATEGORY_ID` | Set/reset category location |
| `PUT /api/stores/ID/products` | Set/reset product override |
| `GET /api/stores/ID/export` | Download JSON layout |
| `POST /api/stores/ID/import/preview` | Validate JSON, return preview |
| `POST /api/stores/ID/import` | Merge/replace layout transactionally |
| `WS /api/live` | Listen for change notifications |

See the Python source for the exact JSON structures. API is intentionally unauthenticated for this personal household tool. No general CORS support is enabled. Data fields are validated, SQL statements use bound parameters, and browser-supplied strings are HTML-escaped before rendering.

## Tests

Run `pytest -q` after `python -m pip install -r requirements.txt pytest httpx`. GitHub Actions runs backend tests on pushes and pull requests. If you add a new data structure to the export file, bump `schema_version` and write migration/import compatibility tests.
