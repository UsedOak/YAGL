# Changelog

## [Unreleased]

### Fixed

- Quantity buttons and duplicate-item increments now adjust the current server quantity atomically, preserving simultaneous taps from multiple browsers. Counts remain within 1-9,999; decrementing never deletes an item.
- Ignore stale state responses after newer refreshes or store changes, including when the selected store is deleted.
- Refresh the shared list when the WebSocket becomes ready, including after reconnecting, to recover missed changes immediately.
- Preserve remembered explicit category choices when re-adding items, so a subsequent rename does not undo a deliberate unassigned category.

### Added

- Optional `quantity_delta: 1` or `-1` in item PATCH requests; absolute `quantity` remains supported, but cannot be combined with a delta.
- Backend regression coverage for concurrent quantities, bounds, validation, live notifications, and category memory.
- Dependency-free Node regression tests for frontend refresh ordering and reconnection, included in CI.

## [0.1.0-rc1] — 2026-11-01

Initial alpha release candidate for third-party GitHub/Docker deployment testing.

- Shared real-time checklist with per-item quantities and Done/clear-completed.
- Optional multiple retailer store profiles with per-device selection.
- Ordered aisles, category keyword memory, and per-product location overrides.
- Version 1 JSON store layout import/export with merge/replace and backup guidance.
- Docker Compose deployment, SQLite persistence, maintenance docs, and automated tests.

Known limits: untested deployment on all NAS flavors; no offline changes, screenshot imports, paid lookups, or community registry; simultaneous edits can race under heavy use.
