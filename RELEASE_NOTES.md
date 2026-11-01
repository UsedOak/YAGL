# YAGL v0.1.0-rc1 — Alpha Release Candidate

**Tag suggestion:** `v0.1.0-rc1`

YAGL — Yet Another Grocery List — is a source-available, self-hosted household shopping list for Docker. One shared list, no accounts, and optional aisle-aware views specific to each browser.

## Included

- Live shared checklist with checkboxes/strikethrough; `Done` clears checked items only.
- Quantity 1 hidden; +/− controls for multiples.
- Per-browser store selection, with universal shared list.
- Customizable physical aisle/zone walking order.
- Deterministic category matching and product-specific store aisle overrides.
- JSON store-layout backup/export and import, preview, merge or replace.
- SQLite persistence, lightweight Docker Compose deployment, documentation, tests, and CI.

## Not included

No accounts, multiple independent lists, retailer API, screenshot parsing, public community map directory, or offline editing. This is an early release candidate; use with backups and expect updates.

## Install like a first-time user

```bash
git clone https://github.com/YOUR-USERNAME/yagl.git
cd yagl
cp .env.example .env
docker compose up -d --build
```

Open `http://SERVER-IP:8080`. The URL will work once the source is published to the chosen repository (replace `YOUR-USERNAME`). A sample store layout lives at `examples/demo-store-map.json` for safe import testing.

## License reminder

MIT plus Commons Clause v1.0. Source-available, not OSI open-source; resale and certain paid services restricted. See LICENSE. Before a public release, the owner should review the copyright holder / licensor attribution and licensing terms.
