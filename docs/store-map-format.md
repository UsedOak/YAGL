# Store map JSON format (schema version 1)

YAGL exports/imports its own `yagl-store-layout` format. It includes a store's physical walking order, reusable category mappings, product location overrides, and relevant remembered product category labels. It does **not** include the active shopping list, list checkmarks, or users (there are no users).

Example:

```json
{
  "format": "yagl-store-layout",
  "schema_version": 1,
  "store": {"name": "Example Walmart", "location": "Example, FL", "store_code": "1234"},
  "aisles": [
    {"code": "A7", "description": "Dry groceries", "sort_order": 0},
    {"code": "Frozen", "description": "Freezer cases", "sort_order": 1}
  ],
  "category_locations": [
    {"category": "Dry Pasta", "keywords": ["pasta", "spaghetti"], "aisle": "A7"},
    {"category": "Frozen Foods", "keywords": ["frozen"], "aisle": "Frozen"}
  ],
  "product_locations": [
    {"product": "SpaghettiOs", "aisle": "A7"}
  ],
  "product_categories": [
    {"product": "SpaghettiOs", "category": "Canned Foods"}
  ]
}
```

Notes:

- `sort_order` represents the desired shopping route, not the physical aisle number.
- Every category/product location must reference an aisle code contained in `aisles`.
- Category names are shared across stores. When an imported category already exists, its existing keywords remain unchanged rather than overwriting definitions used by other store profiles.
- Product category records only populate previously unknown product names; they do not overwrite existing product memory.
- Merge preserves existing target-store mappings and route order; new aisles append to the end.
- Replace deletes only the target store's aisles and their mappings before importing. It does not overwrite the target store's name, its other store profiles, or the shared shopping list.
- Files are currently limited to 512 KB in the UI, with backend validation of fields and reference integrity. Only version 1 is supported.
- Treat shared JSON files as untrusted input. Preview the file, export your own map backup first, and import only intentionally.
