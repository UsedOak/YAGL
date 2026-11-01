# Alpha release candidate testing checklist

This list is intended for the project owner and early self-hosting testers. The app is an alpha, not a finished or commercially supported product.

## Fresh install

- [ ] Clone the public GitHub repository on a separate test system as if you were a first-time user.
- [ ] Copy `.env.example` to `.env`, then run `docker compose up -d --build`.
- [ ] Verify `http://SERVER-IP:8080` works and starts with an empty, usable shopping list without a setup wizard.
- [ ] Restart the container; verify the list and store settings remain intact.

## Shared list

- [ ] Open the same instance on two different devices/browsers.
- [ ] Add `SpaghettiOs` on one device; confirm it appears on the other.
- [ ] Press + twice; quantity should become 3. Press − twice; quantity returns to 1 and its number disappears.
- [ ] Add the same product name again; confirm YAGL offers to increase the existing quantity.
- [ ] Check off one item; it stays visible with a filled checkbox and strikethrough on both devices.
- [ ] Press Done; only checked items disappear from the shared list.

## Store profiles and route

- [ ] Create a store on device A and another store on device B.
- [ ] Select different stores on the two devices; verify neither selection affects the other.
- [ ] Add and reorder aisles (e.g., A20 → A7 → Dairy → Frozen).
- [ ] Map a category, then add a matching product. It should inherit the configured aisle at that store.
- [ ] Assign a different aisle to an individual product; verify the product exception wins.
- [ ] Change the aisle for a category; inheriting products should move, but overridden products should not.
- [ ] Test items with no aisle; they should stay visible in Unmapped items.

## Import/export and recovery

- [ ] Download a JSON backup of an existing store.
- [ ] Import `examples/demo-store-map.json` to a new store using Merge. This layout is deliberately fictional.
- [ ] Preview imported changes before applying them.
- [ ] Import again using Replace and verify the aisle route changes without changing the shared list.
- [ ] Reimport your backup if you want to restore original mappings.
- [ ] Use the documented SQLite backup procedure and check that the backup file exists.

## Deployment / interface

- [ ] Test on an actual iPhone and Android if available, including one-handed checking.
- [ ] Confirm the chosen store remains selected after refreshing that browser.
- [ ] Confirm WebSocket sync works through the production HTTPS reverse proxy.
- [ ] Confirm the site loads in a private browser window (without sharing local preferences).
- [ ] Run `pytest -q` and check GitHub Actions results on push.

Report issues using GitHub's included Bug report template, without real personal or store data in logs.
