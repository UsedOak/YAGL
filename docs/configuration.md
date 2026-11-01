# Store configuration and shopping routes

YAGL needs zero configuration to behave as a checklist. Configuring stores is optional.

## Creating a store

In **Settings → Stores**, create any store name, with optional location and store number. A store is a set of layout information, never a separate shopping list. Select which one to see using the dropdown on the shopping screen. Each browser/device remembers its own choice with localStorage.

## Teaching the physical order

In **Settings → Walking order**, create aisle labels or department zones. Labels are free-form: `A7`, `H5`, `Dairy`, `Frozen`, `Garden Center`, etc. Use the arrow controls to order them from the first aisle you shop to the last. The number is not assumed to indicate order. A common route is shelf-stable goods before refrigerated/frozen, but YAGL does not force that preference.

## Category-to-aisle mapping

In **Settings → Category mapping**, configure categories and comma-separated keyword hints. Seed categories provide a starting point. Once the store has aisles, choose the matching aisle for each category. Future items that match a category keyword can inherit the location for the selected store. Example: category `Dry Pasta`, keywords `pasta, spaghetti, penne` → `A7` at one Walmart, `A12` at another. Editing that category-to-aisle mapping changes the order of all products inheriting it.

This is **deterministic keyword matching**: YAGL does not know every product in existence and cannot guarantee category classification. Inspect and edit ambiguous items as needed; manually chosen categories are remembered for later items with the same name.

## Product exceptions

From the shopping list, choose the `⋯` button next to an item and optionally set its category and aisle. The store-specific location can apply only to that product, or to its entire category. Product exceptions override category mappings at that store. To remove a product exception, choose `Not assigned` for the item-specific location or save a category-wide mapping (which clears its exception).

## Checked items and quantities

The `+` button increases a count. From quantity two upward, the number and `−` button become visible. At quantity one the controls return to only `+`. Checking an item strikes it through without reordering or hiding it. **Done** clears every checked item while leaving unchecked items on the list.

## Browser-specific versus shared

| Shared across devices | Per browser |
| --- | --- |
| List entries, quantities, checked state | Selected store/profile |
| Category definitions and product memory | How items are displayed and sorted |
| Store layouts and mapping changes | Currently open settings panel |

The backend is authoritative and changes propagate over WebSockets. Losing a browser's localStorage only resets the chosen view to the simple list, not your server data.
