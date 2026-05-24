---
title: Canvas state serialization
date: 2026-05-24
status: decided
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
---

# Canvas state serialization

## Inner canvas (per note)

One JSON column added to the existing `notes` table by Sub-project 1's migration:

```sql
ALTER TABLE notes ADD COLUMN canvas_state TEXT;  -- nullable; null → migrate from legacy content
```

`canvas_state` holds a JSON-stringified `InnerCanvasState` (see `src/lib/types.js`). Shape:

```json
{
  "schemaVersion": 1,
  "cards": [
    { "id": "card_...", "type": "text" | "media" | "link",
      "position": { "x": 0, "y": 0 }, "size": { "w": 320, "h": 200 },
      "rotation": 0, "frameId": null,
      "data": { /* variant-specific, see types.js */ } }
  ],
  "frames": [
    { "id": "frame_...", "label": "Key ideas",
      "position": { "x": 0, "y": 0 }, "size": { "w": 800, "h": 400 },
      "isAutoLooseIdeas": false }
  ],
  "connectors": [
    { "id": "conn_...", "sourceCardId": "card_a", "targetCardId": "card_b",
      "kind": "supports" | "contradicts" | "see-also" | "causes" | "example-of" | "free",
      "label": "" }
  ],
  "viewport": { "x": 0, "y": 0, "zoom": 1 }
}
```

## Outer canvas (singleton)

A new SQLite table added by Sub-project 3's migration:

```sql
CREATE TABLE IF NOT EXISTS outer_canvas (
  id INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
  state TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`state` holds a JSON-stringified `OuterCanvasState`:

```json
{
  "schemaVersion": 1,
  "noteCards": [
    { "id": "ncard_...", "noteId": 42,
      "position": { "x": 0, "y": 0 }, "size": { "w": 240, "h": 160 },
      "rotation": 0, "frameId": null,
      "pinned": false, "tags": [], "archived": false }
  ],
  "frames": [
    { "id": "frame_...", "label": "Books",
      "position": { "x": 0, "y": 0 }, "size": { "w": 1200, "h": 600 },
      "isAutoLooseIdeas": false }
  ],
  "connectors": [
    { "id": "conn_...", "sourceCardId": "ncard_a", "targetCardId": "ncard_b",
      "kind": "free", "label": "" }
  ],
  "viewport": { "x": 0, "y": 0, "zoom": 1 }
}
```

## Why a single JSON column instead of normalized tables

- The state is read-and-written wholesale per canvas. No per-card queries from the app side.
- React Flow expects `nodes[]` / `edges[]` arrays in memory — matches the JSON shape exactly.
- Migration cost from today's `notes.content` column is one ALTER TABLE.
- Sub-project 6's Sonnet placement call already wants a flat JSON snapshot; no shape translation needed.

## schemaVersion field

`schemaVersion: 1` baked into every state object. If a future sub-project changes shape, increment + branch in `src/lib/canvas/migrate.js`. Today's migration is "legacy markdown → schemaVersion 1 single TextCard", owned by Sub-project 1.

## Field rules every sub-project must follow

- **Never rename a field.** Extensions to `types.js` must be additive. Removing a field is a `schemaVersion` bump and a migration.
- **Coordinates** are numbers in canvas-space pixels at zoom=1. React Flow handles the transform.
- **IDs** come from `src/lib/canvas/ids.js`. Never construct an id by string concat.
- **Validation** at read boundary via `src/lib/canvas/validators.js`. Invalid state → fall back to empty canvas, never crash.
