# Changelog

## [0.1.0-rc1] — 2026-11-01

Initial alpha release candidate for third-party GitHub/Docker deployment testing.

- Shared real-time checklist with per-item quantities and Done/clear-completed.
- Optional multiple retailer store profiles with per-device selection.
- Ordered aisles, category keyword memory, and per-product location overrides.
- Version 1 JSON store layout import/export with merge/replace and backup guidance.
- Docker Compose deployment, SQLite persistence, maintenance docs, and automated tests.

Known limits: untested deployment on all NAS flavors; no offline changes, screenshot imports, paid lookups, or community registry; simultaneous edits can race under heavy use.
