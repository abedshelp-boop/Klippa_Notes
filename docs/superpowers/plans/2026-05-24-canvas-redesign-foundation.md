# Canvas Redesign — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the cross-cutting decisions and produce shared abstractions that the six follow-on sub-project sessions will branch from.

**Architecture:** This session does NOT implement any sub-project. It commits: (1) two side-by-side engine spike POCs under `experiments/`, (2) three decision docs under `docs/superpowers/decisions/`, (3) JSDoc typedefs in `src/lib/types.js`, (4) shared canvas utility skeletons in `src/lib/canvas/{ids,validators,migrate}.js` with tests. Ends with PR + tag `canvas-foundation-v1` on the merge commit.

**Tech Stack:** JavaScript + JSDoc + TypeScript strict-check (`jsconfig.json` already configured), Vitest, React 19 (inherited from existing app). No new runtime dependencies installed in this session — sub-project 1 installs `@xyflow/react` when it builds the inner canvas.

**Worktree context:** Running inside `.claude/worktrees/canvas-0-foundation` on branch `canvas/0-foundation`, branched off local main HEAD `b576cad`. The approved design spec (`docs/superpowers/specs/2026-05-24-canvas-redesign-design.md`) and seven-session prompts file (`docs/superpowers/plans/2026-05-24-canvas-redesign-session-prompts.md`) were copied in from the main checkout since they were untracked there.

**Engine decision (already locked by context7 research, this plan ratifies it):** **React Flow (`@xyflow/react`)**, MIT licensed, native frames via `type: 'group'` + `parentId` + `extent: 'parent'`, native custom edge types for typed connectors. tldraw rejected primarily for being whiteboard-first (more to disable than to add) and dual-license risk.

---

## File Structure

```
docs/superpowers/
├── specs/2026-05-24-canvas-redesign-design.md          (copied in, untouched)
├── plans/
│   ├── 2026-05-24-canvas-redesign-session-prompts.md   (copied in, untouched)
│   └── 2026-05-24-canvas-redesign-foundation.md        (this file)
└── decisions/
    ├── 2026-05-24-canvas-engine-choice.md              (NEW — engine pick + rationale)
    ├── 2026-05-24-canvas-state-serialization.md        (NEW — exact JSON shape)
    └── 2026-05-24-worktree-convention.md               (NEW — branch naming, merge order)

experiments/canvas-engine-spike/
├── README.md                                            (NEW — how to run each spike)
├── react-flow/index.html                               (NEW — 30-line draggable-card POC)
└── tldraw/index.html                                   (NEW — 30-line draggable-card POC)

src/lib/
├── types.js                                            (NEW — JSDoc typedefs only, no runtime)
└── canvas/
    ├── ids.js                                          (NEW — id generators)
    ├── validators.js                                   (NEW — schema guards)
    ├── migrate.js                                      (NEW — migration scaffold, sub-project 1 fills)
    └── __tests__/
        ├── ids.test.js                                 (NEW)
        ├── validators.test.js                          (NEW)
        └── migrate.test.js                             (NEW)
```

Each file has a single responsibility. `types.js` is documentation-via-types; `ids.js` is pure id generation; `validators.js` is shape guards; `migrate.js` ships as a no-op scaffold so sub-project 1 has a known import target.

---

### Task 1: React Flow spike POC

**Files:**
- Create: `experiments/canvas-engine-spike/react-flow/index.html`

- [ ] **Step 1: Write the POC file**

A self-contained HTML using ESM imports from a CDN. No build step. Open in a browser, drag the card around.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Spike — React Flow draggable card</title>
<style>
  html, body, #root { height: 100%; margin: 0; }
  .card { padding: 12px 16px; background: #fff; border: 1px solid #ddd;
          border-radius: 8px; font-family: system-ui; }
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xyflow/react@12/dist/style.css" />
</head>
<body>
<div id="root"></div>
<script type="importmap">
{ "imports": {
  "react": "https://esm.sh/react@19",
  "react-dom/client": "https://esm.sh/react-dom@19/client",
  "@xyflow/react": "https://esm.sh/@xyflow/react@12?deps=react@19,react-dom@19"
} }
</script>
<script type="module">
import React from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlow, Background, Controls } from '@xyflow/react';

const initialNodes = [
  { id: '1', position: { x: 120, y: 80 },
    data: { label: React.createElement('div', { className: 'card' }, 'Drag me') } },
];

function App() {
  return React.createElement(ReactFlow, { defaultNodes: initialNodes, fitView: true },
    React.createElement(Background, null),
    React.createElement(Controls, null));
}

createRoot(document.getElementById('root')).render(React.createElement(App));
</script>
</body>
</html>
```

- [ ] **Step 2: Sanity-check the file**

Run: `head -2 experiments/canvas-engine-spike/react-flow/index.html`
Expected output: doctype declaration.

No browser open required during the plan execution — the spike is preserved as code-on-disk per the foundation deliverables list. If you want to verify manually, open the file in a browser, see a single draggable card with pan/zoom controls.

- [ ] **Step 3: Commit**

```bash
git add experiments/canvas-engine-spike/react-flow/
git commit -m "spike: react flow draggable card POC"
```

---

### Task 2: tldraw spike POC

**Files:**
- Create: `experiments/canvas-engine-spike/tldraw/index.html`

- [ ] **Step 1: Write the POC file**

Same shape as the React Flow spike — a self-contained HTML using ESM CDN imports. tldraw's API uses `BaseBoxShapeUtil` for custom shapes; the simplest spike just renders the default editor with a placed text shape.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Spike — tldraw draggable card</title>
<style>
  html, body, #root { height: 100%; margin: 0; }
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tldraw@3/tldraw.css" />
</head>
<body>
<div id="root" class="tldraw__editor"></div>
<script type="importmap">
{ "imports": {
  "react": "https://esm.sh/react@19",
  "react-dom/client": "https://esm.sh/react-dom@19/client",
  "tldraw": "https://esm.sh/tldraw@3?deps=react@19,react-dom@19"
} }
</script>
<script type="module">
import React from 'react';
import { createRoot } from 'react-dom/client';
import { Tldraw } from 'tldraw';

function App() {
  return React.createElement(Tldraw, {
    onMount: (editor) => {
      editor.createShape({ type: 'text', x: 120, y: 80, props: { text: 'Drag me' } });
    },
  });
}

createRoot(document.getElementById('root')).render(React.createElement(App));
</script>
</body>
</html>
```

- [ ] **Step 2: Sanity-check the file**

Run: `head -2 experiments/canvas-engine-spike/tldraw/index.html`
Expected output: doctype declaration.

- [ ] **Step 3: Commit**

```bash
git add experiments/canvas-engine-spike/tldraw/
git commit -m "spike: tldraw draggable card POC"
```

---

### Task 3: Spike README

**Files:**
- Create: `experiments/canvas-engine-spike/README.md`

- [ ] **Step 1: Write the README**

```markdown
# Canvas engine spike — 2026-05-24

Two side-by-side draggable-card POCs against the candidate canvas engines for the Deen Notes redesign.

## How to run either

Open `react-flow/index.html` (or `tldraw/index.html`) directly in Chrome. Both fetch their runtime from `esm.sh` / `jsdelivr` — no `npm install` required.

## Outcome

**React Flow won.** See `docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md` for the rationale.

The tldraw POC is preserved verbatim so future readers can see the comparison was real, not a paper exercise.
```

- [ ] **Step 2: Commit**

```bash
git add experiments/canvas-engine-spike/README.md
git commit -m "docs(spike): canvas engine spike README"
```

---

### Task 4: Engine choice decision doc

**Files:**
- Create: `docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md`

- [ ] **Step 1: Write the decision doc**

Content — concise, rationale-first, anti-pattern of long lists avoided:

```markdown
---
title: Canvas engine choice — React Flow
date: 2026-05-24
status: decided
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
---

# Canvas engine — React Flow

## Pick

`@xyflow/react` v12+ (formerly `reactflow`). MIT.

## Why React Flow over tldraw

1. **Spec fit.** The design is "cards + frames + connectors, no freehand." React Flow is a graph editor by default; tldraw is a whiteboard SDK. With React Flow we add primitives we want; with tldraw we hide tools we don't want.
2. **Native frames.** React Flow has first-class node grouping via `type: 'group'` + `parentId` + `extent: 'parent'`. Child nodes move with the parent automatically. This is exactly Sub-project 2's Frame primitive.
3. **Native typed connectors.** Custom edge types with labels are first-class. We get `supports`/`contradicts`/`see also`/`causes`/`example of` by registering edge types — no shape-as-edge hack.
4. **License.** MIT, no MAU watermark, no commercial tier risk. tldraw uses the "tldraw SDK License" with a free-tier watermark and revenue-cap, which is a deployment risk for an Electron desktop app that ships as a standalone product.
5. **React 19 compat.** `@xyflow/react` works with React 19 (the version this project is on).
6. **Smaller surface area.** Less code to disable, faster initial load, fewer ways for a sub-project session to accidentally enable a whiteboard tool we don't want.

## Why not tldraw

- Whiteboard-first feature set (freehand draw, arrow tool, sticky notes, shapes) — we'd spend effort hiding tools that don't match the spec.
- Connectors aren't a primitive — would be implemented as custom shapes, which is more work and worse for placement-model serialization (Sub-project 6).
- License watermark + revenue cap on free tier. Avoidable risk.

## Spike POCs preserved

See [experiments/canvas-engine-spike/](../../experiments/canvas-engine-spike/) — both 30-line POCs are committed so the comparison stays auditable.

## What sub-projects do with this

- Sub-project 1: `npm install @xyflow/react` and build `src/components/InnerCanvas.jsx` against React Flow.
- Sub-project 2: Register custom node types for Frame, MediaCard, LinkCard; custom edge types for the five connector types.
- Sub-project 3: Reuse the same engine for the outer pinboard (`OuterCanvas.jsx`). One engine across both levels.
- Sub-project 6: Serialize node + edge state as the canvas snapshot fed to Sonnet 4.5.

## Reversal cost (if we have to switch later)

Moderate. The state model (in `src/lib/types.js` from this foundation PR) is engine-agnostic — `Card`, `Frame`, `Connector` types don't reference React Flow internals. The render layer would need to be rewritten in each sub-project's component files; state migration is free.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md
git commit -m "docs(decision): pick react flow as canvas engine"
```

---

### Task 5: Canvas state serialization decision doc

**Files:**
- Create: `docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md`

- [ ] **Step 1: Write the doc**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md
git commit -m "docs(decision): canvas state JSON serialization shape"
```

---

### Task 6: Worktree convention decision doc

**Files:**
- Create: `docs/superpowers/decisions/2026-05-24-worktree-convention.md`

- [ ] **Step 1: Write the doc**

```markdown
---
title: Canvas redesign worktree + branch convention
date: 2026-05-24
status: decided
---

# Canvas redesign worktree convention

## Branch naming

`canvas/<n>-<short-name>`, where `<n>` is the sub-project number from `docs/superpowers/plans/2026-05-24-canvas-redesign-session-prompts.md`:

- `canvas/0-foundation` (this PR)
- `canvas/1-inner-foundation`
- `canvas/2-inner-primitives`
- `canvas/3-outer-pinboard`
- `canvas/4-dictation-models`
- `canvas/5-voice-routing`
- `canvas/6-structure-aware-placement`
- `canvas/7-integration`

## Base ref

- Foundation (this PR) branched off main HEAD at the time of session start.
- Sub-projects 1, 3, 4, 5: branch off the **`canvas-foundation-v1` tag** (the merge commit of this PR).
- Sub-project 2: branch off latest main (after Sub-project 1 merges).
- Sub-project 6: branch off latest main (after Sub-projects 1, 2, 5 merge).
- Sub-project 7: branch off latest main after all the others merge.

## Worktree location

Each session creates its worktree under `.claude/worktrees/<branch-suffix>/` in the main repo. Use:

```bash
git worktree add ".claude/worktrees/canvas-1-inner-foundation" -b canvas/1-inner-foundation canvas-foundation-v1
```

Note the explicit base ref — the `using-git-worktrees` skill default may differ.

## CSS namespace prefixes (collision avoidance)

Already declared in session-prompts. Recapped here for one-stop reference:

- Sub-project 1: `.ic-` (inner canvas)
- Sub-project 3: `.oc-` (outer canvas)
- Sub-project 5: `.bubble-` (bubble + picker)
- Sub-projects 2, 4, 6: inherit from the namespaces they extend.

## Shared files at conflict risk

Sub-projects must read these before editing and prefer additive changes:

- `src/App.jsx` — multiple sub-projects swap top-level components.
- `src/lib/types.js` — additive only, never rename a field, never remove a field without a `schemaVersion` bump.
- `package.json` — multiple sub-projects add deps.
- `python-service/main.py` — multiple sub-projects add endpoints.

## Tag

This PR's merge commit is tagged `canvas-foundation-v1` and pushed. That is the canonical branching point for Sub-projects 1, 3, 4, 5.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/decisions/2026-05-24-worktree-convention.md
git commit -m "docs(decision): worktree + branch convention for canvas redesign"
```

---

### Task 7: JSDoc typedefs in `src/lib/types.js`

**Files:**
- Create: `src/lib/types.js`

- [ ] **Step 1: Write the typedefs file**

This file is pure documentation-via-JSDoc, no runtime code. Every sub-project imports types from here using `@typedef` + `@type` JSDoc annotations.

```javascript
// @ts-check
/**
 * Shared canvas typedefs for the Deen Notes canvas redesign.
 *
 * Every sub-project (1, 2, 3, 5, 6) imports types from here.
 *
 * Rule: this file is additive-only. Never rename or remove a field —
 * bump `schemaVersion` in canvas state and write a migration in
 * `src/lib/canvas/migrate.js` instead. See
 * `docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md`.
 *
 * This file has no runtime code; importing it has zero cost.
 */

/**
 * @typedef {{ x: number, y: number }} CanvasPosition
 */

/**
 * @typedef {{ w: number, h: number }} CanvasSize
 */

/**
 * @typedef {{ x: number, y: number, zoom: number }} CanvasViewport
 */

/**
 * @typedef {'supports' | 'contradicts' | 'see-also' | 'causes' | 'example-of' | 'free'} ConnectorKind
 *  `free` is reserved for the outer pinboard (no semantic type at v1, per spec).
 */

/**
 * @typedef {Object} TextCardData
 * @property {string} markdown - Full markdown body, rendered via the existing react-markdown pipeline.
 * @property {'ai-rewrite' | 'verbatim'} [mode] - Capture mode of origin, if dictated. Optional.
 * @property {string} [originalTranscript] - Verbatim audio transcript, kept for per-card mode-flip
 *   re-rewriting (spec: "re-opening a captured card lets the user flip its mode").
 */

/**
 * @typedef {Object} MediaCardData
 * @property {'image' | 'video' | 'audio' | 'file'} kind
 * @property {string} src - Filesystem URL under app.getPath('userData') OR remote URL.
 * @property {string} [alt] - Alt text / caption.
 * @property {string} [mimeType]
 */

/**
 * @typedef {Object} LinkCardData
 * @property {string} url
 * @property {string} [title]
 * @property {string} [description]
 * @property {string} [faviconUrl]
 * @property {string} [previewImageUrl]
 * @property {string} [fetchedAt] - ISO timestamp when the OG preview was fetched.
 */

/**
 * A draggable card inside an inner canvas (one note's contents).
 *
 * @typedef {Object} Card
 * @property {string} id - From `cardId()`.
 * @property {'text' | 'media' | 'link'} type
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {number} rotation - Degrees. 0 unless user rotates.
 * @property {string | null} frameId - Parent frame id, null if free-floating on the canvas.
 * @property {TextCardData | MediaCardData | LinkCardData} data
 */

/**
 * A labeled region that visually clusters cards. Cards with `frameId === frame.id`
 * are children — they move with the frame.
 *
 * @typedef {Object} Frame
 * @property {string} id - From `frameId()`.
 * @property {string} label
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {boolean} isAutoLooseIdeas - True for the "Loose ideas" auto-frame created by
 *   Sub-project 6 on uncertain placement. The frame is hidden from the UI when it has no
 *   children. Only one isAutoLooseIdeas frame per canvas.
 */

/**
 * A typed arrow between two cards.
 *
 * @typedef {Object} Connector
 * @property {string} id - From `connectorId()`.
 * @property {string} sourceCardId
 * @property {string} targetCardId
 * @property {ConnectorKind} kind
 * @property {string} label - Free-text label. Empty string is valid.
 */

/**
 * The full inner-canvas JSON blob stored in `notes.canvas_state`.
 *
 * @typedef {Object} InnerCanvasState
 * @property {number} schemaVersion - Current: 1. Bump on incompatible shape changes.
 * @property {Card[]} cards
 * @property {Frame[]} frames
 * @property {Connector[]} connectors
 * @property {CanvasViewport} viewport - Last-saved viewport so reopening a note feels stable.
 */

/**
 * A note represented as a card on the outer pinboard. The note's actual contents
 * live in its own `InnerCanvasState`; this is just the outer-canvas affordance.
 *
 * @typedef {Object} NoteCard
 * @property {string} id - From `noteCardId()`.
 * @property {number} noteId - Foreign key into the notes table.
 * @property {CanvasPosition} position
 * @property {CanvasSize} size
 * @property {number} rotation
 * @property {string | null} frameId - Parent outer-canvas frame, null if free.
 * @property {boolean} pinned
 * @property {string[]} tags
 * @property {boolean} archived
 */

/**
 * The full outer-canvas JSON blob stored in `outer_canvas.state` (singleton row).
 *
 * @typedef {Object} OuterCanvasState
 * @property {number} schemaVersion
 * @property {NoteCard[]} noteCards
 * @property {Frame[]} frames - Same shape as inner-canvas frames; reused intentionally.
 * @property {Connector[]} connectors - Outer connectors are `kind: 'free'` only at v1 per spec.
 * @property {CanvasViewport} viewport
 */

export {}; // ensure ES module; no runtime exports
```

- [ ] **Step 2: Run typecheck to verify the file parses cleanly**

Run: `npm run typecheck`
Expected: passes with no errors. The file declares typedefs only; no runtime symbols to mistype.

- [ ] **Step 3: Commit**

```bash
git add src/lib/types.js
git commit -m "feat(canvas): shared JSDoc typedefs for canvas state"
```

---

### Task 8: ID generation utility + tests

**Files:**
- Create: `src/lib/canvas/ids.js`
- Create: `src/lib/canvas/__tests__/ids.test.js`

- [ ] **Step 1: Write the failing tests**

```javascript
import { describe, it, expect } from 'vitest';
import { cardId, frameId, connectorId, noteCardId } from '../ids.js';

describe('canvas ids', () => {
  it('cardId returns a string prefixed with "card_"', () => {
    expect(cardId()).toMatch(/^card_[A-Za-z0-9_-]+$/);
  });

  it('frameId returns a string prefixed with "frame_"', () => {
    expect(frameId()).toMatch(/^frame_[A-Za-z0-9_-]+$/);
  });

  it('connectorId returns a string prefixed with "conn_"', () => {
    expect(connectorId()).toMatch(/^conn_[A-Za-z0-9_-]+$/);
  });

  it('noteCardId returns a string prefixed with "ncard_"', () => {
    expect(noteCardId()).toMatch(/^ncard_[A-Za-z0-9_-]+$/);
  });

  it('successive ids are unique', () => {
    const ids = new Set();
    for (let i = 0; i < 1000; i += 1) ids.add(cardId());
    expect(ids.size).toBe(1000);
  });

  it('ids across types do not collide', () => {
    const all = new Set();
    for (let i = 0; i < 250; i += 1) {
      all.add(cardId());
      all.add(frameId());
      all.add(connectorId());
      all.add(noteCardId());
    }
    expect(all.size).toBe(1000);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/lib/canvas/__tests__/ids.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

```javascript
// @ts-check
/**
 * ID generators for canvas entities. Every id MUST come from here —
 * no inline string concat — so collisions are impossible by construction
 * and prefix-based routing in validators stays sound.
 */

/**
 * 12-byte random suffix, base64url-encoded. crypto.randomUUID would also work
 * but produces longer ids; this stays short enough to read in dev console.
 * @returns {string}
 */
function randomSuffix() {
  const bytes = new Uint8Array(9);
  // crypto.getRandomValues exists in Node 19+ (the project's runtime) and all browsers.
  globalThis.crypto.getRandomValues(bytes);
  let s = '';
  for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** @returns {string} */
export function cardId() { return `card_${randomSuffix()}`; }

/** @returns {string} */
export function frameId() { return `frame_${randomSuffix()}`; }

/** @returns {string} */
export function connectorId() { return `conn_${randomSuffix()}`; }

/** @returns {string} */
export function noteCardId() { return `ncard_${randomSuffix()}`; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/lib/canvas/__tests__/ids.test.js`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/canvas/ids.js src/lib/canvas/__tests__/ids.test.js
git commit -m "feat(canvas): id generators for cards/frames/connectors/note-cards"
```

---

### Task 9: Validators + tests

**Files:**
- Create: `src/lib/canvas/validators.js`
- Create: `src/lib/canvas/__tests__/validators.test.js`

- [ ] **Step 1: Write the failing tests**

```javascript
import { describe, it, expect } from 'vitest';
import {
  isInnerCanvasState,
  isOuterCanvasState,
  emptyInnerCanvasState,
  emptyOuterCanvasState,
} from '../validators.js';

describe('canvas validators', () => {
  it('emptyInnerCanvasState round-trips through isInnerCanvasState', () => {
    expect(isInnerCanvasState(emptyInnerCanvasState())).toBe(true);
  });

  it('emptyOuterCanvasState round-trips through isOuterCanvasState', () => {
    expect(isOuterCanvasState(emptyOuterCanvasState())).toBe(true);
  });

  it('rejects null', () => {
    expect(isInnerCanvasState(null)).toBe(false);
    expect(isOuterCanvasState(null)).toBe(false);
  });

  it('rejects wrong schemaVersion', () => {
    const bad = { ...emptyInnerCanvasState(), schemaVersion: 99 };
    expect(isInnerCanvasState(bad)).toBe(false);
  });

  it('rejects missing arrays', () => {
    const bad = { schemaVersion: 1, cards: null, frames: [], connectors: [],
                  viewport: { x: 0, y: 0, zoom: 1 } };
    expect(isInnerCanvasState(bad)).toBe(false);
  });

  it('accepts a populated inner state', () => {
    const good = {
      schemaVersion: 1,
      cards: [{ id: 'card_x', type: 'text', position: { x: 0, y: 0 },
                size: { w: 100, h: 50 }, rotation: 0, frameId: null,
                data: { markdown: 'hi' } }],
      frames: [],
      connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    expect(isInnerCanvasState(good)).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/lib/canvas/__tests__/validators.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```javascript
// @ts-check
/**
 * Shape guards for canvas state. Used at read boundaries (DB load,
 * IPC receive). Invalid state should never throw — fall back to an
 * empty canvas so the app stays usable.
 *
 * Validators are intentionally shallow: they verify the top-level shape
 * and array-ness of children, not every per-card field. Per-card invariants
 * are enforced by the React components that render them.
 */

const SCHEMA_VERSION = 1;

/** @returns {import('../types.js').CanvasViewport} */
function defaultViewport() { return { x: 0, y: 0, zoom: 1 }; }

/** @returns {import('../types.js').InnerCanvasState} */
export function emptyInnerCanvasState() {
  return {
    schemaVersion: SCHEMA_VERSION,
    cards: [],
    frames: [],
    connectors: [],
    viewport: defaultViewport(),
  };
}

/** @returns {import('../types.js').OuterCanvasState} */
export function emptyOuterCanvasState() {
  return {
    schemaVersion: SCHEMA_VERSION,
    noteCards: [],
    frames: [],
    connectors: [],
    viewport: defaultViewport(),
  };
}

/**
 * @param {unknown} v
 * @returns {v is { x: number, y: number, zoom: number }}
 */
function isViewport(v) {
  return !!v && typeof v === 'object'
    && typeof /** @type {any} */ (v).x === 'number'
    && typeof /** @type {any} */ (v).y === 'number'
    && typeof /** @type {any} */ (v).zoom === 'number';
}

/**
 * @param {unknown} v
 * @returns {v is import('../types.js').InnerCanvasState}
 */
export function isInnerCanvasState(v) {
  if (!v || typeof v !== 'object') return false;
  const s = /** @type {any} */ (v);
  return s.schemaVersion === SCHEMA_VERSION
    && Array.isArray(s.cards)
    && Array.isArray(s.frames)
    && Array.isArray(s.connectors)
    && isViewport(s.viewport);
}

/**
 * @param {unknown} v
 * @returns {v is import('../types.js').OuterCanvasState}
 */
export function isOuterCanvasState(v) {
  if (!v || typeof v !== 'object') return false;
  const s = /** @type {any} */ (v);
  return s.schemaVersion === SCHEMA_VERSION
    && Array.isArray(s.noteCards)
    && Array.isArray(s.frames)
    && Array.isArray(s.connectors)
    && isViewport(s.viewport);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/lib/canvas/__tests__/validators.test.js`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/canvas/validators.js src/lib/canvas/__tests__/validators.test.js
git commit -m "feat(canvas): schema guards + empty-state factories"
```

---

### Task 10: Migration scaffold + tests

**Files:**
- Create: `src/lib/canvas/migrate.js`
- Create: `src/lib/canvas/__tests__/migrate.test.js`

- [ ] **Step 1: Write the failing tests**

```javascript
import { describe, it, expect } from 'vitest';
import { migrateInnerCanvasState, CURRENT_SCHEMA_VERSION } from '../migrate.js';
import { emptyInnerCanvasState, isInnerCanvasState } from '../validators.js';

describe('canvas migrate', () => {
  it('CURRENT_SCHEMA_VERSION is 1', () => {
    expect(CURRENT_SCHEMA_VERSION).toBe(1);
  });

  it('null input migrates to empty inner state', () => {
    const result = migrateInnerCanvasState(null);
    expect(isInnerCanvasState(result)).toBe(true);
    expect(result.cards).toEqual([]);
  });

  it('a valid current-version state passes through unchanged', () => {
    const state = emptyInnerCanvasState();
    const result = migrateInnerCanvasState(state);
    expect(result).toEqual(state);
  });

  it('invalid input migrates to empty state', () => {
    const result = migrateInnerCanvasState({ junk: true });
    expect(isInnerCanvasState(result)).toBe(true);
    expect(result.cards).toEqual([]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/lib/canvas/__tests__/migrate.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the scaffold implementation**

This file is a SCAFFOLD. Sub-project 1 fills in the legacy-markdown-to-single-TextCard migration. Foundation only ships the version constant + a null-safe identity migration so sub-projects have a known import target.

```javascript
// @ts-check
/**
 * Canvas state migration. Foundation ships only the scaffold; sub-project 1
 * adds `migrateLegacyMarkdown(noteContent)` which converts a pre-redesign
 * note's `content` field into a one-TextCard `InnerCanvasState`.
 *
 * If you're sub-project 1 reading this: that function goes here, and
 * `App.jsx`'s migration block (see existing pattern with `deen.migrate.*`
 * localStorage flags) gates it behind `deen.migrate.canvas.v1`.
 *
 * @module
 */

import { isInnerCanvasState, emptyInnerCanvasState } from './validators.js';

export const CURRENT_SCHEMA_VERSION = 1;

/**
 * Bring any persisted inner-canvas state forward to the current schema.
 * Null, invalid, or unknown-shape input → empty canvas (never throws).
 *
 * @param {unknown} raw
 * @returns {import('../types.js').InnerCanvasState}
 */
export function migrateInnerCanvasState(raw) {
  if (isInnerCanvasState(raw)) return raw;
  // Future: branch on raw.schemaVersion when bumping past 1.
  return emptyInnerCanvasState();
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/lib/canvas/__tests__/migrate.test.js`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/canvas/migrate.js src/lib/canvas/__tests__/migrate.test.js
git commit -m "feat(canvas): migration scaffold + CURRENT_SCHEMA_VERSION"
```

---

### Task 11: Full verification pass

**Files:** (no edits — verification only)

- [ ] **Step 1: Run the full typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors. types.js, ids.js, validators.js, migrate.js all parse cleanly.

- [ ] **Step 2: Run the full test suite**

Run: `npm test`
Expected: PASS — all existing tests still green, plus the 16 new tests from this PR (6 ids + 6 validators + 4 migrate).

- [ ] **Step 3: Verify no error-swallowing try/catch was introduced**

Run: `grep -rn "catch" src/lib/canvas/` (or your equivalent)
Expected: zero matches. No try/catch in the foundation utilities — they're shallow pure functions.

- [ ] **Step 4: Confirm no new console.log left behind**

Run: `grep -rn "console.log" src/lib/canvas/ src/lib/types.js`
Expected: zero matches.

---

### Task 12: Open PR

**Files:** (no edits)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin canvas/0-foundation
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "foundation: canvas redesign — shared types + engine choice" --body "$(cat <<'EOF'
## Summary

Foundation PR for the canvas redesign (spec: `docs/superpowers/specs/2026-05-24-canvas-redesign-design.md`). This PR locks the cross-cutting decisions and produces shared abstractions that the six follow-on sub-project sessions will branch from. It does NOT implement any sub-project.

**Engine pick: React Flow (`@xyflow/react`).** MIT licensed, native frames via node grouping, native typed connectors via custom edge types. tldraw was spiked side-by-side and rejected (whiteboard-first surface, license watermark, connectors not a primitive). Both spike POCs preserved under `experiments/canvas-engine-spike/`.

### What's in this PR

- **Decision docs** under `docs/superpowers/decisions/`:
  - `2026-05-24-canvas-engine-choice.md` — engine pick + rationale
  - `2026-05-24-canvas-state-serialization.md` — exact JSON shape per canvas
  - `2026-05-24-worktree-convention.md` — branch naming, base refs, merge order
- **Spike POCs** under `experiments/canvas-engine-spike/{react-flow,tldraw}/`
- **Shared types** in `src/lib/types.js` — JSDoc typedefs for `Card`, `Frame`, `Connector`, `InnerCanvasState`, `OuterCanvasState`, `NoteCard`
- **Shared utilities** in `src/lib/canvas/`:
  - `ids.js` — `cardId()`, `frameId()`, `connectorId()`, `noteCardId()` with prefix routing
  - `validators.js` — `isInnerCanvasState`, `isOuterCanvasState`, empty-state factories
  - `migrate.js` — scaffold + `CURRENT_SCHEMA_VERSION`; sub-project 1 fills in legacy-markdown migration

### Out of scope (other sessions)

- Inner canvas component / TextCard rendering → Sub-project 1
- Frames, MediaCard, LinkCard, Connectors → Sub-project 2
- Outer pinboard → Sub-project 3
- Dictation, model swaps, TTS → Sub-project 4
- Voice routing, bubble redesign → Sub-project 5
- Structure-aware placement → Sub-project 6

### Post-merge

Tag the merge commit `canvas-foundation-v1` and push the tag. Sub-projects 1, 3, 4, 5 will branch from it.

## Test plan

- [ ] `npm run typecheck` passes (JSDoc + TS strict on the new files)
- [ ] `npm test` passes (existing + 16 new tests)
- [ ] Manual: open `experiments/canvas-engine-spike/react-flow/index.html` in Chrome — a draggable card renders with pan/zoom controls

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Note the PR URL — report back to the user**

The PR URL is printed by `gh pr create`. Save it; it goes in the final session report.

---

### Task 13: Tag (post-merge — note for the reviewer)

This task is NOT executed in this session. It runs after the PR is merged to main by the reviewer.

After merge:

```bash
git checkout main
git pull
git tag canvas-foundation-v1
git push origin canvas-foundation-v1
```

The tag pin is what Sub-projects 1, 3, 4, 5 use as their `git worktree add` base ref.

---

## Self-Review

**1. Spec coverage:** The foundation deliverables list from the session prompt is:
- One PR titled "foundation: ..." ✓ Task 12
- Engine POC files under `experiments/canvas-engine-spike/` ✓ Tasks 1, 2, 3
- Engine choice decision doc ✓ Task 4
- `src/lib/types.js` + `src/lib/canvas/*.js` skeletons ✓ Tasks 7, 8, 9, 10
- Tag `canvas-foundation-v1` on merge commit ✓ Task 13 (post-merge note)
- All tests passing ✓ Task 11

Plus the two additional decision docs (state serialization, worktree convention) that the foundation should produce per the session prompt's "Decisions you must lock in this session" list ✓ Tasks 5, 6.

**2. Placeholder scan:** No TBDs, no "implement later", every code block is complete. The migrate.js scaffold is explicitly a scaffold (sub-project 1's territory is called out in the file's own docstring) — that's deliberate, not a placeholder.

**3. Type consistency:**
- `ConnectorKind` literal values: `'supports' | 'contradicts' | 'see-also' | 'causes' | 'example-of' | 'free'` — used identically in types.js and the serialization decision doc. ✓
- `schemaVersion: 1` — used in validators.js `SCHEMA_VERSION` constant, in `migrate.js` `CURRENT_SCHEMA_VERSION`, and quoted in the serialization doc. All point to `1`. ✓
- ID prefix conventions (`card_`, `frame_`, `conn_`, `ncard_`) — same in ids.js tests, in the validators logic context, and in the serialization decision doc examples. ✓
- `Frame` shape is reused across inner + outer canvas — types.js documents this; serialization doc calls it out. ✓
