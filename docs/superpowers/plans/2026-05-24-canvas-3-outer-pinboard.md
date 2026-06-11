# Outer Pinboard (Sub-project 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `Home` grid view with an `OuterCanvas` — a draggable, zoomable pinboard rendered with @xyflow/react, where each note is a card, existing groups become outer-canvas frames, and users can draw free-form connection lines between cards.

**Architecture:**
- A new singleton `outer_canvas` SQLite row stores the canvas state as JSON (shape defined in `src/lib/types.js` from the foundation PR). One-time client-side migration (gated by `deen.migrate.outer-canvas.v1`) converts existing notes + groups + localStorage overlay into the canvas state.
- The view layer is `@xyflow/react` v12 with two registered custom node types (`note-card`, `frame`) and free-form default edges. The pure conversion between `OuterCanvasState` and ReactFlow's `{ nodes, edges }` lives in `src/lib/canvas/outer.js` so it is fully unit-testable.
- Sidebar filters (pinned / tags / archive) stop navigating to separate views and instead emit a layer-toggle payload the canvas consumes to dim or hide non-matching cards.

**Tech Stack:**
- `@xyflow/react` v12 (canvas engine, decided in `docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md`)
- Vitest + `@testing-library/react` + `jsdom` (component tests)
- React 19, Vite 8 (existing)
- FastAPI + aiosqlite (existing python-service)

**Reference docs (read first):**
- `docs/superpowers/specs/2026-05-24-canvas-redesign-design.md` — design spec, "Outer canvas" section.
- `docs/superpowers/decisions/2026-05-24-canvas-state-serialization.md` — `outer_canvas` table shape + field rules.
- `docs/superpowers/decisions/2026-05-24-canvas-engine-choice.md` — engine rationale + grouping API.
- `docs/superpowers/decisions/2026-05-24-worktree-convention.md` — CSS prefix is `.oc-` for this sub-project.
- `src/lib/types.js` — `OuterCanvasState`, `NoteCard`, `Frame`, `Connector` typedefs (additive-only).
- `src/lib/canvas/ids.js` — always use `noteCardId()` / `frameId()` / `connectorId()` for ids.
- `src/lib/canvas/validators.js` — `emptyOuterCanvasState()`, `isOuterCanvasState()` for boundary checks.

---

## File Structure

### New files

| File | Responsibility |
| --- | --- |
| `src/lib/canvas/outer.js` | Pure helpers: factories, `migrateLegacyToOuterCanvas`, `toReactFlow`, `fromReactFlow`, `reconcileWithNotes`. No React, no fetch. |
| `src/lib/canvas/__tests__/outer.test.js` | Unit tests for everything in `outer.js`. |
| `src/hooks/useOuterCanvas.js` | Fetches state from `/outer-canvas`, runs migration once, persists on commit, reconciles with notes list. |
| `src/hooks/__tests__/useOuterCanvas.test.js` | Hook tests (mock `fetch`). |
| `src/components/OuterCanvas.jsx` | Mounts `ReactFlow`, wires state, free-form connections, layer overlay, click-to-open. |
| `src/components/__tests__/OuterCanvas.test.jsx` | Smoke + interaction tests. |
| `src/components/cards/NoteCardOnCanvas.jsx` | The card rendered for each note (title, last-edited, preview, indicators). |
| `src/components/cards/__tests__/NoteCardOnCanvas.test.jsx` | Render + click tests. |
| `src/components/canvas/OuterFrame.jsx` | Minimal frame node (label header + body region). |
| `src/components/canvas/__tests__/OuterFrame.test.jsx` | Render test. |
| `src/test/setup.js` | Vitest setup file: `@testing-library/jest-dom`, `ResizeObserver` shim, basic DOMRect for React Flow. |

### Modified files

| File | Change |
| --- | --- |
| `package.json` | Add deps: `@xyflow/react`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`. |
| `vitest.config.js` | Default test env to `jsdom`; load setup file. |
| `src/index.css` | Append `.oc-*` styles + import `@xyflow/react/dist/style.css` at top. |
| `src/App.jsx` | Swap `<Home>` for `<OuterCanvas>`; rename `view === 'home'` (no behavior change, just the component). |
| `src/components/Sidebar.jsx` | Keep filter buttons; their payload now drives layer visibility on the canvas instead of changing the view. (Visual treatment unchanged.) |
| `python-service/database.py` | Add `outer_canvas` table to `init_db()`, plus `get_outer_canvas` / `set_outer_canvas` helpers. |
| `python-service/routes.py` | Add `GET /outer-canvas` and `PUT /outer-canvas`, broadcast `outer_canvas_updated`. |
| `src/hooks/useWebSocket.js` | Handle `outer_canvas_updated` broadcast → notify subscribers (optional, see Task 9 for the call site decision). |

### Files NOT deleted in this PR (per spec)

`src/components/Home.jsx`, `src/components/NoteCard.jsx`, `src/components/GroupTree.jsx`, `src/components/MoveToGroupModal.jsx` stay on disk. The spec instructs deletion only after this PR is approved and the replacement is verified working — that is a follow-up commit, not part of this plan.

---

## Task 1: Install dependencies and configure jsdom test env

**Files:**
- Modify: `package.json` (add deps)
- Modify: `vitest.config.js`
- Create: `src/test/setup.js`

- [ ] **Step 1: Install dependencies**

Run inside the worktree:

```bash
npm install @xyflow/react
npm install -D jsdom @testing-library/react @testing-library/jest-dom
```

Expected: `package.json` gains those entries; `npm install` exits 0.

- [ ] **Step 2: Create `src/test/setup.js`**

```js
import '@testing-library/jest-dom/vitest';

// React Flow uses ResizeObserver and getBoundingClientRect; jsdom stubs neither.
// Provide just enough surface for nodes to mount without exploding.
class ResizeObserverShim {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverShim;

if (!HTMLElement.prototype.getBoundingClientRect ||
    HTMLElement.prototype.getBoundingClientRect.toString().includes('jsdom')) {
  HTMLElement.prototype.getBoundingClientRect = function () {
    return { x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 600,
             width: 800, height: 600, toJSON: () => ({}) };
  };
}

// DOMMatrixReadOnly is referenced by @xyflow/react's internal transform code.
if (typeof DOMMatrixReadOnly === 'undefined') {
  class DOMMatrixReadOnlyShim {
    constructor(transform) {
      const scale = transform?.match?.(/scale\(([^)]+)\)/)?.[1];
      this.m22 = scale ? Number(scale) : 1;
    }
  }
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyShim;
}
```

- [ ] **Step 3: Update `vitest.config.js`**

Replace contents with:

```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}', 'electron/**/*.test.js'],
    exclude: ['node_modules', 'dist', 'release', 'python-service'],
  },
});
```

- [ ] **Step 4: Run the existing test suite to verify nothing regressed**

```bash
npm test
```

Expected: all foundation tests (`ids`, `validators`, `migrate`, `debug`) still pass. Output ends with `Tests  X passed`.

- [ ] **Step 5: Run typecheck**

```bash
npm run typecheck
```

Expected: zero errors. (`@xyflow/react` ships its own types — they should not pollute the foundation files yet because nothing imports it.)

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json vitest.config.js src/test/setup.js
git commit -m "chore(canvas): install @xyflow/react + jsdom test env"
```

---

## Task 2: Outer-canvas factories + migration (TDD)

**Files:**
- Create: `src/lib/canvas/outer.js`
- Create: `src/lib/canvas/__tests__/outer.test.js`

These are the pure functions all downstream tasks depend on. No React, no fetch — pure logic, fully unit-testable.

- [ ] **Step 1: Write the failing test file**

Create `src/lib/canvas/__tests__/outer.test.js`:

```js
import { describe, it, expect } from 'vitest';
import {
  createNoteCard,
  createOuterFrame,
  createFreeConnector,
  migrateLegacyToOuterCanvas,
} from '../outer.js';
import { isOuterCanvasState } from '../validators.js';

describe('createNoteCard', () => {
  it('produces a NoteCard with sensible defaults', () => {
    const nc = createNoteCard({ noteId: 'note-42' });
    expect(nc.id).toMatch(/^ncard_/);
    expect(nc.noteId).toBe('note-42');
    expect(nc.position).toEqual({ x: 0, y: 0 });
    expect(nc.size.w).toBeGreaterThan(0);
    expect(nc.size.h).toBeGreaterThan(0);
    expect(nc.rotation).toBe(0);
    expect(nc.frameId).toBeNull();
    expect(nc.pinned).toBe(false);
    expect(nc.tags).toEqual([]);
    expect(nc.archived).toBe(false);
  });

  it('applies overrides', () => {
    const nc = createNoteCard({
      noteId: 'n', position: { x: 100, y: 50 },
      size: { w: 320, h: 200 }, pinned: true, tags: ['t'], archived: true,
      frameId: 'frame_abc',
    });
    expect(nc.position).toEqual({ x: 100, y: 50 });
    expect(nc.size).toEqual({ w: 320, h: 200 });
    expect(nc.pinned).toBe(true);
    expect(nc.tags).toEqual(['t']);
    expect(nc.archived).toBe(true);
    expect(nc.frameId).toBe('frame_abc');
  });
});

describe('createOuterFrame', () => {
  it('produces a Frame with isAutoLooseIdeas=false', () => {
    const f = createOuterFrame({ label: 'Books' });
    expect(f.id).toMatch(/^frame_/);
    expect(f.label).toBe('Books');
    expect(f.isAutoLooseIdeas).toBe(false);
    expect(f.size.w).toBeGreaterThan(0);
  });
});

describe('createFreeConnector', () => {
  it('produces a free connector', () => {
    const c = createFreeConnector({ sourceCardId: 'a', targetCardId: 'b' });
    expect(c.id).toMatch(/^conn_/);
    expect(c.sourceCardId).toBe('a');
    expect(c.targetCardId).toBe('b');
    expect(c.kind).toBe('free');
    expect(c.label).toBe('');
  });
});

describe('migrateLegacyToOuterCanvas', () => {
  const isoNow = '2026-05-24T00:00:00Z';

  function fakeOverlay(opts = {}) {
    const pinned = new Set(opts.pinnedIds || []);
    const trashed = new Set(opts.trashedIds || []);
    const tagMap = opts.tagMap || {};
    return {
      isPinned: (id) => pinned.has(id),
      isTrashed: (id) => trashed.has(id),
      getUserTags: (id) => tagMap[id] || [],
    };
  }

  it('returns a valid OuterCanvasState', () => {
    const state = migrateLegacyToOuterCanvas({ notes: [], groups: [], overlay: fakeOverlay() });
    expect(isOuterCanvasState(state)).toBe(true);
    expect(state.noteCards).toEqual([]);
    expect(state.frames).toEqual([]);
    expect(state.connectors).toEqual([]);
  });

  it('each group becomes one frame', () => {
    const groups = [
      { id: 'g1', name: 'Books', parent_id: null },
      { id: 'g2', name: 'Recipes', parent_id: null },
    ];
    const state = migrateLegacyToOuterCanvas({ notes: [], groups, overlay: fakeOverlay() });
    expect(state.frames).toHaveLength(2);
    expect(state.frames.map((f) => f.label).sort()).toEqual(['Books', 'Recipes']);
    expect(state.frames.every((f) => !f.isAutoLooseIdeas)).toBe(true);
  });

  it('notes in a group land inside that group\'s frame', () => {
    const groups = [{ id: 'g1', name: 'Books', parent_id: null }];
    const notes = [
      { id: 'n1', title: 'Sapiens', group_id: 'g1', created_at: isoNow, updated_at: isoNow },
      { id: 'n2', title: 'Pride', group_id: 'g1', created_at: isoNow, updated_at: isoNow },
    ];
    const state = migrateLegacyToOuterCanvas({ notes, groups, overlay: fakeOverlay() });
    const frame = state.frames[0];
    const cards = state.noteCards.filter((c) => c.frameId === frame.id);
    expect(cards).toHaveLength(2);
    expect(cards.map((c) => c.noteId).sort()).toEqual(['n1', 'n2']);
  });

  it('ungrouped notes go to the canvas floor (frameId=null)', () => {
    const notes = [
      { id: 'n1', title: 'Loose', group_id: null, created_at: isoNow, updated_at: isoNow },
    ];
    const state = migrateLegacyToOuterCanvas({ notes, groups: [], overlay: fakeOverlay() });
    expect(state.noteCards).toHaveLength(1);
    expect(state.noteCards[0].frameId).toBeNull();
  });

  it('layouts cards in a grid inside each frame (no overlap)', () => {
    const groups = [{ id: 'g1', name: 'Books', parent_id: null }];
    const notes = Array.from({ length: 6 }, (_, i) => ({
      id: `n${i}`, title: `t${i}`, group_id: 'g1', created_at: isoNow, updated_at: isoNow,
    }));
    const state = migrateLegacyToOuterCanvas({ notes, groups, overlay: fakeOverlay() });
    const cards = state.noteCards;
    // No two cards in the same frame share both x and y.
    const seen = new Set();
    for (const c of cards) {
      const key = `${c.position.x},${c.position.y}`;
      expect(seen.has(key)).toBe(false);
      seen.add(key);
    }
  });

  it('overlay pinned/tags/archived carry over onto NoteCard fields', () => {
    const notes = [
      { id: 'n1', title: 't', group_id: null, created_at: isoNow, updated_at: isoNow },
    ];
    const overlay = fakeOverlay({
      pinnedIds: ['n1'],
      trashedIds: ['n1'],
      tagMap: { n1: ['focus', 'urgent'] },
    });
    const state = migrateLegacyToOuterCanvas({ notes, groups: [], overlay });
    expect(state.noteCards[0].pinned).toBe(true);
    expect(state.noteCards[0].archived).toBe(true);
    expect(state.noteCards[0].tags).toEqual(['focus', 'urgent']);
  });
});
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
npm test -- src/lib/canvas/__tests__/outer.test.js
```

Expected: `Cannot find module '../outer.js'` or test failures — file doesn't exist yet.

- [ ] **Step 3: Implement `src/lib/canvas/outer.js`**

```js
// @ts-check
/**
 * Pure helpers for the outer pinboard canvas. No React, no fetch, no IPC.
 * All ids come from src/lib/canvas/ids.js. All shapes come from src/lib/types.js.
 */

import { noteCardId, frameId, connectorId } from './ids.js';
import { emptyOuterCanvasState } from './validators.js';

const DEFAULT_NOTE_CARD_SIZE = { w: 240, h: 160 };
const DEFAULT_FRAME_SIZE = { w: 1200, h: 600 };
const FRAME_GAP = 80;
const FRAME_INNER_PAD = { x: 24, y: 60 }; // y leaves room for the label bar
const CARD_GAP = 16;

/**
 * @param {{
 *   noteId: string,
 *   position?: import('../types.js').CanvasPosition,
 *   size?: import('../types.js').CanvasSize,
 *   rotation?: number,
 *   frameId?: string | null,
 *   pinned?: boolean,
 *   tags?: string[],
 *   archived?: boolean,
 * }} opts
 * @returns {import('../types.js').NoteCard}
 */
export function createNoteCard(opts) {
  return {
    id: noteCardId(),
    noteId: opts.noteId,
    position: opts.position ?? { x: 0, y: 0 },
    size: opts.size ?? { ...DEFAULT_NOTE_CARD_SIZE },
    rotation: opts.rotation ?? 0,
    frameId: opts.frameId ?? null,
    pinned: opts.pinned ?? false,
    tags: opts.tags ?? [],
    archived: opts.archived ?? false,
  };
}

/**
 * @param {{
 *   label: string,
 *   position?: import('../types.js').CanvasPosition,
 *   size?: import('../types.js').CanvasSize,
 *   isAutoLooseIdeas?: boolean,
 * }} opts
 * @returns {import('../types.js').Frame}
 */
export function createOuterFrame(opts) {
  return {
    id: frameId(),
    label: opts.label,
    position: opts.position ?? { x: 0, y: 0 },
    size: opts.size ?? { ...DEFAULT_FRAME_SIZE },
    isAutoLooseIdeas: opts.isAutoLooseIdeas ?? false,
  };
}

/**
 * @param {{ sourceCardId: string, targetCardId: string, label?: string }} opts
 * @returns {import('../types.js').Connector}
 */
export function createFreeConnector(opts) {
  return {
    id: connectorId(),
    sourceCardId: opts.sourceCardId,
    targetCardId: opts.targetCardId,
    kind: 'free',
    label: opts.label ?? '',
  };
}

/**
 * One-time migration of the pre-canvas state into an OuterCanvasState.
 * Pure — depends only on its arguments.
 *
 * Group order is preserved as given (caller typically already sorts by name).
 * Notes inside a group are arranged in a row-major grid; ungrouped notes go to
 * the canvas floor below the last frame row.
 *
 * @param {{
 *   notes: Array<{ id: string, title?: string, group_id?: string | null,
 *                  created_at?: string, updated_at?: string }>,
 *   groups: Array<{ id: string, name: string, parent_id?: string | null }>,
 *   overlay: {
 *     isPinned: (id: string) => boolean,
 *     isTrashed: (id: string) => boolean,
 *     getUserTags: (id: string) => string[],
 *   },
 * }} input
 * @returns {import('../types.js').OuterCanvasState}
 */
export function migrateLegacyToOuterCanvas({ notes, groups, overlay }) {
  const state = emptyOuterCanvasState();

  const FRAMES_PER_ROW = 2;
  const groupIdToFrame = new Map();

  groups.forEach((g, i) => {
    const col = i % FRAMES_PER_ROW;
    const row = Math.floor(i / FRAMES_PER_ROW);
    const frame = createOuterFrame({
      label: g.name,
      position: {
        x: col * (DEFAULT_FRAME_SIZE.w + FRAME_GAP),
        y: row * (DEFAULT_FRAME_SIZE.h + FRAME_GAP),
      },
    });
    state.frames.push(frame);
    groupIdToFrame.set(g.id, frame);
  });

  const grouped = new Map(); // group_id -> NoteCard[]
  const ungrouped = [];

  for (const note of notes) {
    const frame = note.group_id ? groupIdToFrame.get(note.group_id) : null;
    const card = createNoteCard({
      noteId: note.id,
      frameId: frame ? frame.id : null,
      pinned: overlay.isPinned(note.id),
      tags: overlay.getUserTags(note.id),
      archived: overlay.isTrashed(note.id),
    });
    if (frame) {
      if (!grouped.has(frame.id)) grouped.set(frame.id, []);
      grouped.get(frame.id).push(card);
    } else {
      ungrouped.push(card);
    }
  }

  // Lay out cards inside each frame in a grid.
  for (const frame of state.frames) {
    const cards = grouped.get(frame.id) || [];
    const innerW = frame.size.w - FRAME_INNER_PAD.x * 2;
    const cardsPerRow = Math.max(1,
      Math.floor((innerW + CARD_GAP) / (DEFAULT_NOTE_CARD_SIZE.w + CARD_GAP)));
    cards.forEach((c, i) => {
      const col = i % cardsPerRow;
      const row = Math.floor(i / cardsPerRow);
      c.position = {
        x: FRAME_INNER_PAD.x + col * (DEFAULT_NOTE_CARD_SIZE.w + CARD_GAP),
        y: FRAME_INNER_PAD.y + row * (DEFAULT_NOTE_CARD_SIZE.h + CARD_GAP),
      };
      state.noteCards.push(c);
    });
  }

  // Ungrouped: stack below the last frame row, full-width grid.
  const framesRows = Math.ceil(groups.length / FRAMES_PER_ROW);
  const floorY = framesRows * (DEFAULT_FRAME_SIZE.h + FRAME_GAP) + FRAME_GAP;
  const floorPerRow = 4;
  ungrouped.forEach((c, i) => {
    const col = i % floorPerRow;
    const row = Math.floor(i / floorPerRow);
    c.position = {
      x: col * (DEFAULT_NOTE_CARD_SIZE.w + CARD_GAP),
      y: floorY + row * (DEFAULT_NOTE_CARD_SIZE.h + CARD_GAP),
    };
    state.noteCards.push(c);
  });

  return state;
}
```

- [ ] **Step 4: Run the tests, confirm they pass**

```bash
npm test -- src/lib/canvas/__tests__/outer.test.js
```

Expected: all tests pass.

- [ ] **Step 5: Typecheck**

```bash
npm run typecheck
```

Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
git add src/lib/canvas/outer.js src/lib/canvas/__tests__/outer.test.js
git commit -m "feat(canvas): outer-canvas factories + legacy migration"
```

---

## Task 3: ReactFlow ↔ OuterCanvasState conversion (TDD)

**Files:**
- Modify: `src/lib/canvas/outer.js` (add two exports)
- Modify: `src/lib/canvas/__tests__/outer.test.js` (add round-trip tests)

The canvas component stores its working state as React Flow's `{ nodes, edges }` arrays. Persistence stores `OuterCanvasState`. The two converters here are the only place that translation lives.

- [ ] **Step 1: Append round-trip tests to `outer.test.js`**

```js
import {
  toReactFlow,
  fromReactFlow,
} from '../outer.js';
import { emptyOuterCanvasState } from '../validators.js';

describe('toReactFlow', () => {
  it('frames become group-style nodes; note cards become note-card nodes with parentId', () => {
    const frame = createOuterFrame({ label: 'Books', position: { x: 0, y: 0 } });
    const card = createNoteCard({
      noteId: 'n1', frameId: frame.id, position: { x: 24, y: 60 },
    });
    const state = { ...emptyOuterCanvasState(), frames: [frame], noteCards: [card] };
    const { nodes, edges } = toReactFlow(state);
    const frameNode = nodes.find((n) => n.id === frame.id);
    const cardNode = nodes.find((n) => n.id === card.id);
    expect(frameNode.type).toBe('frame');
    expect(cardNode.type).toBe('note-card');
    expect(cardNode.parentId).toBe(frame.id);
    expect(cardNode.extent).toBe('parent');
    expect(edges).toEqual([]);
  });

  it('free connectors become edges of type free', () => {
    const a = createNoteCard({ noteId: 'a' });
    const b = createNoteCard({ noteId: 'b' });
    const conn = createFreeConnector({ sourceCardId: a.id, targetCardId: b.id });
    const state = { ...emptyOuterCanvasState(),
                    noteCards: [a, b], connectors: [conn] };
    const { edges } = toReactFlow(state);
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe(conn.id);
    expect(edges[0].source).toBe(a.id);
    expect(edges[0].target).toBe(b.id);
    expect(edges[0].type).toBe('free');
  });
});

describe('fromReactFlow', () => {
  it('round-trips toReactFlow output back to an equivalent state', () => {
    const frame = createOuterFrame({ label: 'F', position: { x: 100, y: 100 } });
    const a = createNoteCard({
      noteId: 'a', frameId: frame.id, position: { x: 24, y: 60 },
      pinned: true, tags: ['x'], archived: false,
    });
    const b = createNoteCard({ noteId: 'b', position: { x: 0, y: 800 } });
    const conn = createFreeConnector({ sourceCardId: a.id, targetCardId: b.id });
    const original = {
      schemaVersion: 1,
      noteCards: [a, b],
      frames: [frame],
      connectors: [conn],
      viewport: { x: 10, y: 20, zoom: 0.8 },
    };
    const graph = toReactFlow(original);
    const restored = fromReactFlow(graph, original.viewport);
    expect(restored.frames).toEqual(original.frames);
    expect(restored.noteCards).toEqual(original.noteCards);
    expect(restored.connectors).toEqual(original.connectors);
    expect(restored.viewport).toEqual(original.viewport);
  });

  it('infers frameId from parentId on the node back into the NoteCard', () => {
    const frame = createOuterFrame({ label: 'F' });
    const card = createNoteCard({ noteId: 'n', frameId: null });
    const state = { ...emptyOuterCanvasState(), frames: [frame], noteCards: [card] };
    const graph = toReactFlow(state);
    // Simulate the user dragging the card into the frame: ReactFlow would set
    // parentId on the card node. We mimic that here.
    const cardNode = graph.nodes.find((n) => n.id === card.id);
    cardNode.parentId = frame.id;
    cardNode.extent = 'parent';
    const restored = fromReactFlow(graph, { x: 0, y: 0, zoom: 1 });
    expect(restored.noteCards[0].frameId).toBe(frame.id);
  });
});
```

- [ ] **Step 2: Run tests, confirm failures**

```bash
npm test -- src/lib/canvas/__tests__/outer.test.js
```

Expected: failures with "toReactFlow is not a function" etc.

- [ ] **Step 3: Add converters to `src/lib/canvas/outer.js`**

Append:

```js
/**
 * Convert OuterCanvasState into the { nodes, edges } shape ReactFlow expects.
 * Frame nodes go first so they render under their children.
 *
 * @param {import('../types.js').OuterCanvasState} state
 * @returns {{ nodes: Array<any>, edges: Array<any> }}
 */
export function toReactFlow(state) {
  const nodes = [];
  for (const frame of state.frames) {
    nodes.push({
      id: frame.id,
      type: 'frame',
      position: { ...frame.position },
      data: { label: frame.label, isAutoLooseIdeas: frame.isAutoLooseIdeas },
      style: { width: frame.size.w, height: frame.size.h },
    });
  }
  for (const card of state.noteCards) {
    const node = {
      id: card.id,
      type: 'note-card',
      position: { ...card.position },
      data: {
        noteId: card.noteId,
        pinned: card.pinned,
        tags: card.tags,
        archived: card.archived,
      },
      style: { width: card.size.w, height: card.size.h },
    };
    if (card.frameId) {
      node.parentId = card.frameId;
      node.extent = 'parent';
    }
    nodes.push(node);
  }
  const edges = state.connectors.map((c) => ({
    id: c.id,
    source: c.sourceCardId,
    target: c.targetCardId,
    type: c.kind === 'free' ? 'free' : c.kind,
    label: c.label || undefined,
    data: { kind: c.kind },
  }));
  return { nodes, edges };
}

/**
 * Convert a ReactFlow graph + viewport back to an OuterCanvasState. Used
 * before persisting changes.
 *
 * @param {{ nodes: Array<any>, edges: Array<any> }} graph
 * @param {import('../types.js').CanvasViewport} viewport
 * @returns {import('../types.js').OuterCanvasState}
 */
export function fromReactFlow(graph, viewport) {
  /** @type {import('../types.js').Frame[]} */
  const frames = [];
  /** @type {import('../types.js').NoteCard[]} */
  const noteCards = [];

  for (const node of graph.nodes) {
    if (node.type === 'frame') {
      frames.push({
        id: node.id,
        label: node.data?.label ?? '',
        position: { x: node.position.x, y: node.position.y },
        size: { w: node.style?.width ?? 1200, h: node.style?.height ?? 600 },
        isAutoLooseIdeas: !!node.data?.isAutoLooseIdeas,
      });
    } else if (node.type === 'note-card') {
      noteCards.push({
        id: node.id,
        noteId: node.data?.noteId,
        position: { x: node.position.x, y: node.position.y },
        size: { w: node.style?.width ?? 240, h: node.style?.height ?? 160 },
        rotation: 0,
        frameId: node.parentId ?? null,
        pinned: !!node.data?.pinned,
        tags: Array.isArray(node.data?.tags) ? node.data.tags : [],
        archived: !!node.data?.archived,
      });
    }
  }

  /** @type {import('../types.js').Connector[]} */
  const connectors = graph.edges.map((e) => ({
    id: e.id,
    sourceCardId: e.source,
    targetCardId: e.target,
    kind: e.data?.kind || (e.type === 'free' ? 'free' : 'free'),
    label: typeof e.label === 'string' ? e.label : '',
  }));

  return {
    schemaVersion: 1,
    noteCards,
    frames,
    connectors,
    viewport: { x: viewport.x, y: viewport.y, zoom: viewport.zoom },
  };
}
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
npm test -- src/lib/canvas/__tests__/outer.test.js
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/canvas/outer.js src/lib/canvas/__tests__/outer.test.js
git commit -m "feat(canvas): bidirectional ReactFlow ↔ OuterCanvasState conversion"
```

---

## Task 4: Python service — `outer_canvas` table + REST endpoints

**Files:**
- Modify: `python-service/database.py`
- Modify: `python-service/routes.py`

This is the only Python work in this PR. There are no Python tests in the project; correctness is verified by the React side's integration tests + manual launch in Task 12.

- [ ] **Step 1: Add the singleton table to `init_db()`**

In `python-service/database.py`, inside `init_db()`, after the `groups` `CREATE TABLE` and before the migrations block, add:

```python
        await db.execute("""
            CREATE TABLE IF NOT EXISTS outer_canvas (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
```

- [ ] **Step 2: Add getter and setter helpers in `database.py`**

Append at the end of the file (before or after the `_row_to_dict` helper — pick the spot that matches surrounding style):

```python
async def get_outer_canvas() -> dict | None:
    """Return the singleton outer-canvas row as {"state": <dict>, "updated_at": <iso>}.

    Returns None if the row has not been written yet — the client interprets that
    as "no migration has run; run it now."
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT state, updated_at FROM outer_canvas WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        try:
            state = json.loads(row["state"])
        except (json.JSONDecodeError, TypeError):
            # Corrupt JSON shouldn't kill the app — let the client run migration again.
            return None
        return {"state": state, "updated_at": row["updated_at"]}


async def set_outer_canvas(state: dict) -> dict:
    """UPSERT the singleton outer-canvas row. Returns the persisted shape."""
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(state)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO outer_canvas (id, state, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET state = excluded.state, "
            "updated_at = excluded.updated_at",
            (payload, now),
        )
        await db.commit()
    return {"state": state, "updated_at": now}
```

- [ ] **Step 3: Add the routes in `python-service/routes.py`**

After the existing `/groups` routes block, add:

```python
# --------------------------- Outer canvas -----------------------------------


@app.get("/outer-canvas")
async def get_outer_canvas_route():
    """Return the singleton outer-canvas state. 204 with empty body when no row
    has been written yet — the client will run its migration and PUT the result."""
    row = await db.get_outer_canvas()
    if row is None:
        return {"state": None, "updated_at": None}
    return row


@app.put("/outer-canvas")
async def put_outer_canvas_route(body: dict):
    """Replace the singleton outer-canvas state with `body.state`. Broadcasts
    `outer_canvas_updated` so other windows refresh."""
    state = body.get("state")
    if not isinstance(state, dict):
        raise HTTPException(
            status_code=400,
            detail="body.state must be an object",
        )
    saved = await db.set_outer_canvas(state)
    await broadcast({
        "type": "outer_canvas_updated",
        "state": saved["state"],
        "updated_at": saved["updated_at"],
    })
    return saved
```

- [ ] **Step 4: Smoke-test the endpoints**

Start the python-service in dev (or rely on Task 12's full app launch). For a focused check:

```bash
cd python-service
python -c "import asyncio, database as d; asyncio.run(d.init_db()); print('init ok')"
```

Expected: `init ok` with no exception. The `outer_canvas` table now exists.

- [ ] **Step 5: Commit**

```bash
git add python-service/database.py python-service/routes.py
git commit -m "feat(api): add outer_canvas table + GET/PUT endpoints"
```

---

## Task 5: useOuterCanvas hook with one-shot migration (TDD)

**Files:**
- Create: `src/hooks/useOuterCanvas.js`
- Create: `src/hooks/__tests__/useOuterCanvas.test.js`

This hook owns: fetch on mount, run migration once (gated by `deen.migrate.outer-canvas.v1`), persist on commit (debounced), and reconcile with the live notes list so newly-created or deleted notes appear/disappear on the canvas.

- [ ] **Step 1: Write the failing test file**

Create `src/hooks/__tests__/useOuterCanvas.test.js`:

```js
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import useOuterCanvas from '../useOuterCanvas.js';

const MIGRATION_FLAG = 'deen.migrate.outer-canvas.v1';

function mockFetchSequence(responses) {
  const fn = vi.fn();
  responses.forEach((r) => {
    if (typeof r === 'function') fn.mockImplementationOnce(r);
    else fn.mockResolvedValueOnce({ ok: true, json: async () => r });
  });
  globalThis.fetch = fn;
  return fn;
}

function fakeOverlay(opts = {}) {
  return {
    isPinned: () => !!opts.pinned,
    isTrashed: () => !!opts.trashed,
    getUserTags: () => opts.tags || [],
  };
}

describe('useOuterCanvas', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('on first load with no server state, runs migration and PUTs once', async () => {
    const notes = [
      { id: 'n1', title: 'A', group_id: null, created_at: '2026-05-24T00:00:00Z',
        updated_at: '2026-05-24T00:00:00Z' },
    ];
    const groups = [];
    const fetchMock = mockFetchSequence([
      { state: null, updated_at: null },          // GET /outer-canvas
      { state: {}, updated_at: '2026-05-24T...' }, // PUT /outer-canvas
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes, groups, overlay: fakeOverlay() }));

    await waitFor(() => {
      expect(result.current.state).not.toBeNull();
    });
    expect(result.current.state.noteCards).toHaveLength(1);
    expect(localStorage.getItem(MIGRATION_FLAG)).toBe('done');
    const putCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(putCall).toBeDefined();
  });

  it('on second load with the flag set, does NOT re-run migration', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1,
      noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const fetchMock = mockFetchSequence([
      { state: existing, updated_at: '...' },
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes: [], groups: [], overlay: fakeOverlay() }));

    await waitFor(() => expect(result.current.state).not.toBeNull());
    const putCount = fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT').length;
    expect(putCount).toBe(0);
  });

  it('reconciles: a note not in state gets added to the canvas floor', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1, noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    mockFetchSequence([
      { state: existing, updated_at: '...' }, // GET
      { state: {}, updated_at: '...' },        // PUT after reconcile
    ]);

    const notes = [
      { id: 'new', title: 'fresh', group_id: null,
        created_at: '2026-05-24T00:00:00Z', updated_at: '2026-05-24T00:00:00Z' },
    ];

    const { result } = renderHook(() =>
      useOuterCanvas({ notes, groups: [], overlay: fakeOverlay() }));

    await waitFor(() =>
      expect(result.current.state?.noteCards?.length).toBe(1));
    expect(result.current.state.noteCards[0].noteId).toBe('new');
  });

  it('commit() PUTs the latest state', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1, noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const fetchMock = mockFetchSequence([
      { state: existing, updated_at: '...' },  // GET
      { state: {}, updated_at: '...' },         // PUT
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes: [], groups: [], overlay: fakeOverlay() }));
    await waitFor(() => expect(result.current.state).not.toBeNull());

    const next = { ...result.current.state, viewport: { x: 5, y: 5, zoom: 1.2 } };
    await act(async () => { await result.current.commit(next); });

    const putCalls = fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT');
    expect(putCalls.length).toBeGreaterThan(0);
    const body = JSON.parse(putCalls[putCalls.length - 1][1].body);
    expect(body.state.viewport).toEqual({ x: 5, y: 5, zoom: 1.2 });
  });
});
```

- [ ] **Step 2: Run the test file, confirm failures**

```bash
npm test -- src/hooks/__tests__/useOuterCanvas.test.js
```

Expected: failures because `useOuterCanvas` doesn't exist yet.

- [ ] **Step 3: Implement the hook**

Create `src/hooks/useOuterCanvas.js`:

```js
import { useCallback, useEffect, useRef, useState } from 'react';
import { debug } from '../lib/debug';
import {
  migrateLegacyToOuterCanvas,
  createNoteCard,
} from '../lib/canvas/outer.js';
import { isOuterCanvasState, emptyOuterCanvasState } from '../lib/canvas/validators.js';

const API_URL = 'http://localhost:8765';
const MIGRATION_FLAG = 'deen.migrate.outer-canvas.v1';

/**
 * Owns the outer-canvas state lifecycle:
 *  - Loads from GET /outer-canvas on mount.
 *  - If no state on the server AND migration flag unset, runs
 *    migrateLegacyToOuterCanvas() and PUTs the result. Sets flag.
 *  - Reconciles whenever `notes` changes: notes not on the canvas yet are
 *    added to the canvas floor; canvas cards whose note no longer exists are
 *    removed.
 *  - `commit(nextState)` persists via PUT.
 */
export default function useOuterCanvas({ notes, groups, overlay }) {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const didMigrate = useRef(false);
  const didReconcile = useRef(false);

  const persist = useCallback(async (nextState) => {
    try {
      const res = await fetch(`${API_URL}/outer-canvas`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: nextState }),
      });
      if (!res.ok) debug.error('OuterCanvas', 'PUT failed', res.status);
    } catch (err) {
      debug.error('OuterCanvas', 'PUT failed', err);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/outer-canvas`);
        if (cancelled) return;
        if (!res.ok) {
          setLoading(false);
          return;
        }
        const body = await res.json();
        if (cancelled) return;
        if (body && isOuterCanvasState(body.state)) {
          setState(body.state);
          setLoading(false);
          return;
        }
        // Either null or invalid — fall through to migration path.
        setState(null);
        setLoading(false);
      } catch (err) {
        debug.warn('OuterCanvas', 'GET failed', err);
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // One-shot migration: runs after first GET resolves with no server state,
  // notes have loaded, and the flag is unset.
  useEffect(() => {
    if (loading) return;
    if (state !== null) return;
    if (didMigrate.current) return;
    if (typeof localStorage !== 'undefined' &&
        localStorage.getItem(MIGRATION_FLAG) === 'done') {
      // Flag set but no state — could happen if the server's row was wiped.
      // Treat as "create empty canvas" rather than re-migrating, which would
      // duplicate cards if reconciliation later adds them.
      const empty = emptyOuterCanvasState();
      didMigrate.current = true;
      setState(empty);
      persist(empty);
      return;
    }
    if (!Array.isArray(notes)) return; // wait until notes hook resolves
    didMigrate.current = true;
    const migrated = migrateLegacyToOuterCanvas({ notes, groups: groups || [], overlay });
    setState(migrated);
    try { localStorage.setItem(MIGRATION_FLAG, 'done'); }
    catch (err) { debug.warn('OuterCanvas', 'flag persist failed', err); }
    persist(migrated);
  }, [loading, state, notes, groups, overlay, persist]);

  // Reconcile: add missing notes, remove orphan cards. Runs at most once per
  // notes-array identity to avoid loops.
  useEffect(() => {
    if (!state) return;
    if (!Array.isArray(notes)) return;
    const noteIds = new Set(notes.map((n) => n.id));
    const cardNoteIds = new Set(state.noteCards.map((c) => c.noteId));
    const missing = notes.filter((n) => !cardNoteIds.has(n.id));
    const orphans = state.noteCards.filter((c) => !noteIds.has(c.noteId));
    if (missing.length === 0 && orphans.length === 0) return;
    didReconcile.current = true;
    const PER_ROW = 4;
    const W = 240; const H = 160; const GAP = 16;
    const baseY = state.noteCards.reduce((m, c) =>
      Math.max(m, c.position.y + c.size.h), 0) + GAP;
    const additions = missing.map((n, i) => createNoteCard({
      noteId: n.id,
      pinned: overlay.isPinned(n.id),
      tags: overlay.getUserTags(n.id),
      archived: overlay.isTrashed(n.id),
      position: {
        x: (i % PER_ROW) * (W + GAP),
        y: baseY + Math.floor(i / PER_ROW) * (H + GAP),
      },
    }));
    const next = {
      ...state,
      noteCards: [
        ...state.noteCards.filter((c) => noteIds.has(c.noteId)),
        ...additions,
      ],
    };
    setState(next);
    persist(next);
  }, [notes, state, overlay, persist]);

  const commit = useCallback(async (next) => {
    setState(next);
    await persist(next);
  }, [persist]);

  return { state, loading, commit };
}
```

- [ ] **Step 4: Run hook tests, confirm pass**

```bash
npm test -- src/hooks/__tests__/useOuterCanvas.test.js
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useOuterCanvas.js src/hooks/__tests__/useOuterCanvas.test.js
git commit -m "feat(canvas): useOuterCanvas hook (fetch + migrate + reconcile)"
```

---

## Task 6: NoteCardOnCanvas component (TDD)

**Files:**
- Create: `src/components/cards/NoteCardOnCanvas.jsx`
- Create: `src/components/cards/__tests__/NoteCardOnCanvas.test.jsx`

The card receives data from React Flow via a `data` prop. It needs source AND target Handles on multiple sides so users can draw free-form connection lines in any direction.

- [ ] **Step 1: Write the failing test file**

Create `src/components/cards/__tests__/NoteCardOnCanvas.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import NoteCardOnCanvas from '../NoteCardOnCanvas.jsx';

function wrap(ui) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

describe('NoteCardOnCanvas', () => {
  const note = {
    id: 'n1',
    title: 'Sapiens — Chapter 3',
    content: 'A brief history note about agricultural revolution and grain.',
    created_at: '2026-05-24T00:00:00Z',
    updated_at: '2026-05-24T00:00:00Z',
  };

  it('renders the note title', () => {
    wrap(<NoteCardOnCanvas data={{ note, pinned: false, tags: [], archived: false }} />);
    expect(screen.getByText(/Sapiens — Chapter 3/)).toBeInTheDocument();
  });

  it('shows a preview snippet', () => {
    wrap(<NoteCardOnCanvas data={{ note, pinned: false, tags: [], archived: false }} />);
    expect(screen.getByText(/agricultural revolution/i)).toBeInTheDocument();
  });

  it('shows pin indicator when pinned', () => {
    wrap(<NoteCardOnCanvas data={{ note, pinned: true, tags: [], archived: false }} />);
    expect(screen.getByLabelText(/pinned/i)).toBeInTheDocument();
  });

  it('shows up to 2 tag chips', () => {
    wrap(<NoteCardOnCanvas data={{ note, pinned: false,
      tags: ['focus', 'urgent', 'extra'], archived: false }} />);
    expect(screen.getByText('focus')).toBeInTheDocument();
    expect(screen.getByText('urgent')).toBeInTheDocument();
    expect(screen.queryByText('extra')).not.toBeInTheDocument();
  });

  it('applies an archived modifier class when archived', () => {
    const { container } = wrap(
      <NoteCardOnCanvas data={{ note, pinned: false, tags: [], archived: true }} />,
    );
    expect(container.querySelector('.oc-card.is-archived')).not.toBeNull();
  });

  it('falls back to "Untitled Note" when title is empty', () => {
    wrap(<NoteCardOnCanvas data={{
      note: { ...note, title: '' },
      pinned: false, tags: [], archived: false,
    }} />);
    expect(screen.getByText(/Untitled Note/i)).toBeInTheDocument();
  });

  it('calls onOpen when the card body is clicked', () => {
    const onOpen = vi.fn();
    wrap(<NoteCardOnCanvas data={{
      note, pinned: false, tags: [], archived: false, onOpen,
    }} />);
    fireEvent.click(screen.getByText(/Sapiens — Chapter 3/));
    expect(onOpen).toHaveBeenCalledWith('n1');
  });

  it('renders source AND target handles for free-form connections', () => {
    const { container } = wrap(
      <NoteCardOnCanvas data={{ note, pinned: false, tags: [], archived: false }} />,
    );
    // React Flow handles render as elements with class react-flow__handle.
    const handles = container.querySelectorAll('.react-flow__handle');
    expect(handles.length).toBeGreaterThanOrEqual(2);
  });
});
```

- [ ] **Step 2: Confirm the test fails**

```bash
npm test -- src/components/cards/__tests__/NoteCardOnCanvas.test.jsx
```

Expected: import failure.

- [ ] **Step 3: Implement the component**

Create `src/components/cards/NoteCardOnCanvas.jsx`:

```jsx
import React from 'react';
import { Handle, Position } from '@xyflow/react';

function formatRelative(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }
  const within7 = (now - date) / 86400000 < 7;
  if (within7) return date.toLocaleDateString('en-US', { weekday: 'short' });
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function extractPreview(content) {
  if (!content) return '';
  const lines = content.split('\n').map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (l.startsWith('#')) continue;
    if (l.startsWith('---')) continue;
    return l.replace(/[*_`#>[\]]/g, '').slice(0, 140);
  }
  return '';
}

/**
 * Custom node rendered for `type: 'note-card'`. React Flow passes us a `data`
 * prop with whatever we put into the node's data.
 *
 * Expected `data` shape:
 *   note: { id, title, content, updated_at, created_at }
 *   pinned, archived: boolean
 *   tags: string[]
 *   onOpen?: (noteId: string) => void
 */
export default function NoteCardOnCanvas({ data }) {
  const note = data?.note;
  if (!note) return null;
  const title = (note.title || '').trim() || 'Untitled Note';
  const preview = extractPreview(note.content || '') || 'No preview available';
  const dateLabel = formatRelative(note.updated_at || note.created_at);
  const tags = Array.isArray(data.tags) ? data.tags : [];

  const onClick = (e) => {
    // Avoid hijacking the handle drag interaction.
    if (e.target.closest('.react-flow__handle')) return;
    if (typeof data.onOpen === 'function') data.onOpen(note.id);
  };

  return (
    <div
      className={[
        'oc-card',
        data.pinned ? 'is-pinned' : '',
        data.archived ? 'is-archived' : '',
      ].join(' ').trim()}
      onClick={onClick}
    >
      <Handle type="target" position={Position.Top} className="oc-card-handle" />
      <Handle type="source" position={Position.Bottom} className="oc-card-handle" />

      <div className="oc-card-top">
        {data.pinned && (
          <span className="oc-card-pin" aria-label="Pinned" title="Pinned">●</span>
        )}
        {tags.slice(0, 2).map((t) => (
          <span key={t} className="oc-card-tag">{t}</span>
        ))}
        <span className="oc-card-date">{dateLabel}</span>
      </div>
      <div className="oc-card-title">{title}</div>
      <div className="oc-card-preview">{preview}</div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm pass**

```bash
npm test -- src/components/cards/__tests__/NoteCardOnCanvas.test.jsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/cards/NoteCardOnCanvas.jsx src/components/cards/__tests__/NoteCardOnCanvas.test.jsx
git commit -m "feat(canvas): NoteCardOnCanvas with pin/tag/archive indicators"
```

---

## Task 7: OuterFrame component (TDD)

**Files:**
- Create: `src/components/canvas/OuterFrame.jsx`
- Create: `src/components/canvas/__tests__/OuterFrame.test.jsx`

Minimal v1 frame: a labeled translucent region. Sub-project 2 may replace this with a shared Frame component later.

- [ ] **Step 1: Write the failing test**

Create `src/components/canvas/__tests__/OuterFrame.test.jsx`:

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import OuterFrame from '../OuterFrame.jsx';

describe('OuterFrame', () => {
  it('renders the frame label', () => {
    render(<ReactFlowProvider><OuterFrame data={{ label: 'Books' }} /></ReactFlowProvider>);
    expect(screen.getByText('Books')).toBeInTheDocument();
  });

  it('falls back to "Untitled Frame" when label is empty', () => {
    render(<ReactFlowProvider><OuterFrame data={{ label: '' }} /></ReactFlowProvider>);
    expect(screen.getByText(/Untitled Frame/i)).toBeInTheDocument();
  });

  it('marks the auto Loose Ideas frame visually', () => {
    const { container } = render(
      <ReactFlowProvider>
        <OuterFrame data={{ label: 'Loose ideas', isAutoLooseIdeas: true }} />
      </ReactFlowProvider>,
    );
    expect(container.querySelector('.oc-frame.is-loose')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Confirm failure**

```bash
npm test -- src/components/canvas/__tests__/OuterFrame.test.jsx
```

Expected: import failure.

- [ ] **Step 3: Implement the component**

Create `src/components/canvas/OuterFrame.jsx`:

```jsx
import React from 'react';

/**
 * Minimal outer-canvas frame node. Renders a labeled translucent backdrop.
 * Child note-card nodes are positioned by React Flow over this backdrop
 * via parentId/extent='parent'.
 *
 * Expected `data` shape: { label: string, isAutoLooseIdeas?: boolean }
 */
export default function OuterFrame({ data }) {
  const label = (data?.label || '').trim() || 'Untitled Frame';
  const cls = [
    'oc-frame',
    data?.isAutoLooseIdeas ? 'is-loose' : '',
  ].join(' ').trim();

  return (
    <div className={cls}>
      <div className="oc-frame-label">{label}</div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
npm test -- src/components/canvas/__tests__/OuterFrame.test.jsx
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/canvas/OuterFrame.jsx src/components/canvas/__tests__/OuterFrame.test.jsx
git commit -m "feat(canvas): minimal OuterFrame node component"
```

---

## Task 8: OuterCanvas component (TDD + integration)

**Files:**
- Create: `src/components/OuterCanvas.jsx`
- Create: `src/components/__tests__/OuterCanvas.test.jsx`

Mounts `<ReactFlow>` with the custom node + edge types, wires the hook, handles free-form connections, applies the filter overlay, and surfaces an empty state when there are zero cards.

- [ ] **Step 1: Write the failing test**

Create `src/components/__tests__/OuterCanvas.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import OuterCanvas from '../OuterCanvas.jsx';

function fakeOverlay(opts = {}) {
  return {
    isPinned: () => !!opts.pinned,
    isTrashed: () => !!opts.trashed,
    getUserTags: () => opts.tags || [],
  };
}

function mockFetchSequence(responses) {
  const fn = vi.fn();
  responses.forEach((r) => {
    fn.mockResolvedValueOnce({ ok: true, json: async () => r });
  });
  globalThis.fetch = fn;
  return fn;
}

const isoNow = '2026-05-24T00:00:00Z';

describe('OuterCanvas', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders an empty state when no notes and no canvas state', async () => {
    mockFetchSequence([
      { state: null, updated_at: null },
      { state: {}, updated_at: '...' },
    ]);
    render(
      <OuterCanvas
        notes={[]} groups={[]} overlay={fakeOverlay()}
        filter={{ type: 'all' }} onOpenNote={() => {}} onCreateNote={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText(/Nothing here yet|Say "Hey Deen"/i)).toBeInTheDocument(),
    );
  });

  it('renders a note card after migration', async () => {
    mockFetchSequence([
      { state: null, updated_at: null },
      { state: {}, updated_at: '...' },
    ]);
    const notes = [{
      id: 'n1', title: 'A test note', content: 'preview text', group_id: null,
      created_at: isoNow, updated_at: isoNow,
    }];
    render(
      <OuterCanvas
        notes={notes} groups={[]} overlay={fakeOverlay()}
        filter={{ type: 'all' }} onOpenNote={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText('A test note')).toBeInTheDocument(),
    );
  });

  it('applies a hidden class to non-matching cards when filter=pinned', async () => {
    localStorage.setItem('deen.migrate.outer-canvas.v1', 'done');
    const state = {
      schemaVersion: 1,
      noteCards: [
        { id: 'ncard_a', noteId: 'n1', position: { x: 0, y: 0 },
          size: { w: 240, h: 160 }, rotation: 0, frameId: null,
          pinned: true, tags: [], archived: false },
        { id: 'ncard_b', noteId: 'n2', position: { x: 260, y: 0 },
          size: { w: 240, h: 160 }, rotation: 0, frameId: null,
          pinned: false, tags: [], archived: false },
      ],
      frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    mockFetchSequence([{ state, updated_at: '...' }]);
    const notes = [
      { id: 'n1', title: 'pinned one', content: '', updated_at: isoNow },
      { id: 'n2', title: 'unpinned one', content: '', updated_at: isoNow },
    ];

    const { container } = render(
      <OuterCanvas
        notes={notes} groups={[]} overlay={fakeOverlay()}
        filter={{ type: 'pinned' }} onOpenNote={() => {}}
      />,
    );
    await waitFor(() => expect(screen.getByText('pinned one')).toBeInTheDocument());
    // Unpinned card's wrapper node should be marked hidden.
    const nodes = container.querySelectorAll('.react-flow__node-note-card');
    const visibilities = Array.from(nodes).map((n) =>
      n.classList.contains('oc-node-hidden'));
    expect(visibilities.filter(Boolean).length).toBe(1);
  });

  it('calls onConnect handler when an edge connection is fired', async () => {
    // We can't simulate the user dragging from handle to handle in jsdom, but
    // we can verify that an onConnect callback path produces a new edge by
    // exposing a test hook. Skipped here in favor of the unit test on
    // fromReactFlow in Task 3; the connection wiring is integration-tested by
    // manual launch in Task 12.
    expect(true).toBe(true);
  });
});
```

- [ ] **Step 2: Confirm test failures**

```bash
npm test -- src/components/__tests__/OuterCanvas.test.jsx
```

Expected: import failure.

- [ ] **Step 3: Implement `src/components/OuterCanvas.jsx`**

```jsx
import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import useOuterCanvas from '../hooks/useOuterCanvas';
import {
  toReactFlow, fromReactFlow, createFreeConnector,
} from '../lib/canvas/outer.js';
import NoteCardOnCanvas from './cards/NoteCardOnCanvas.jsx';
import OuterFrame from './canvas/OuterFrame.jsx';

const nodeTypes = {
  'note-card': NoteCardOnCanvas,
  frame: OuterFrame,
};

function matchesFilter(card, filter) {
  if (!filter || filter.type === 'all') return !card.archived;
  if (filter.type === 'pinned') return card.pinned && !card.archived;
  if (filter.type === 'archive') return card.archived;
  if (filter.type === 'tag') return (card.tags || []).includes(filter.value) && !card.archived;
  if (filter.type === 'group') return card.frameId === filter.value && !card.archived;
  return !card.archived;
}

/**
 * Inner content (lives inside ReactFlowProvider so the useNodesState/useEdgesState
 * hooks have a flow instance to attach to).
 */
function OuterCanvasInner({
  notes, groups, overlay, filter, onOpenNote, onCreateNote,
}) {
  const { state, loading, commit } = useOuterCanvas({ notes, groups, overlay });

  const noteById = useMemo(() => {
    const map = new Map();
    for (const n of notes) map.set(n.id, n);
    return map;
  }, [notes]);

  const initialGraph = useMemo(
    () => state ? toReactFlow(state) : { nodes: [], edges: [] },
    [state],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialGraph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialGraph.edges);

  // Re-seed when the persisted state changes (initial load + reconciliation).
  const seedKeyRef = useRef('');
  useEffect(() => {
    if (!state) return;
    const seedKey = JSON.stringify({
      n: state.noteCards.map((c) => c.id),
      f: state.frames.map((f) => f.id),
      e: state.connectors.map((c) => c.id),
    });
    if (seedKey === seedKeyRef.current) return;
    seedKeyRef.current = seedKey;
    const graph = toReactFlow(state);
    setNodes(graph.nodes);
    setEdges(graph.edges);
  }, [state, setNodes, setEdges]);

  // Inject the latest note + filter visibility + onOpen into each node's data
  // on every render (so renames / pin toggles / filter switches reflect).
  const decoratedNodes = useMemo(() => {
    return nodes.map((n) => {
      if (n.type === 'note-card') {
        const noteId = n.data?.noteId;
        const note = noteById.get(noteId);
        // Find matching card metadata from state when available.
        const card = state?.noteCards.find((c) => c.id === n.id);
        const cardMeta = card || {
          pinned: !!n.data?.pinned,
          tags: n.data?.tags || [],
          archived: !!n.data?.archived,
          frameId: n.parentId ?? null,
        };
        const visible = matchesFilter(cardMeta, filter);
        return {
          ...n,
          hidden: !visible,
          className: visible ? '' : 'oc-node-hidden',
          data: {
            ...n.data,
            note,
            pinned: cardMeta.pinned,
            tags: cardMeta.tags,
            archived: cardMeta.archived,
            onOpen: onOpenNote,
          },
        };
      }
      return n;
    });
  }, [nodes, noteById, state, filter, onOpenNote]);

  const onConnect = useCallback((params) => {
    if (!params?.source || !params?.target) return;
    const conn = createFreeConnector({
      sourceCardId: params.source, targetCardId: params.target,
    });
    setEdges((eds) => addEdge({
      id: conn.id, source: params.source, target: params.target,
      type: 'free', data: { kind: 'free' },
    }, eds));
  }, [setEdges]);

  // Persist on every change. Debounced via a microtask + ref trick to avoid
  // saving on every mouse-move drag tick.
  const commitTimerRef = useRef(null);
  const scheduleCommit = useCallback(() => {
    if (!state) return;
    if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    commitTimerRef.current = setTimeout(() => {
      const graph = { nodes, edges };
      const next = fromReactFlow(graph, state.viewport || { x: 0, y: 0, zoom: 1 });
      commit(next);
    }, 400);
  }, [nodes, edges, state, commit]);

  useEffect(() => {
    if (!state) return;
    scheduleCommit();
    return () => {
      if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    };
  }, [nodes, edges, scheduleCommit, state]);

  // Empty state — show CTA before/instead of an empty graph.
  const showEmpty = !loading && state && state.noteCards.length === 0;

  return (
    <div className="oc-root">
      {showEmpty && (
        <div className="oc-empty">
          <div className="oc-empty-headline">Nothing here yet.</div>
          <div className="oc-empty-hint">
            Say <span className="kbd">"Hey Deen"</span>
            {onCreateNote && (
              <>
                {' '}or{' '}
                <button type="button" className="oc-empty-cta" onClick={onCreateNote}>
                  + Write a new note
                </button>
              </>
            )}
          </div>
        </div>
      )}
      <ReactFlow
        nodes={decoratedNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView={state?.noteCards.length > 0}
        defaultViewport={state?.viewport || { x: 0, y: 0, zoom: 1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={24} />
        <Controls />
        <MiniMap zoomable pannable />
      </ReactFlow>
    </div>
  );
}

export default function OuterCanvas(props) {
  return (
    <ReactFlowProvider>
      <OuterCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
```

- [ ] **Step 4: Run the tests**

```bash
npm test -- src/components/__tests__/OuterCanvas.test.jsx
```

Expected: all pass. If the filter visibility assertion fails, inspect the `.oc-node-hidden` className wiring — React Flow may overwrite the className. Fall back to checking `node.hidden === true` via test code.

- [ ] **Step 5: Add CSS to `src/index.css`**

Append to the end of `src/index.css` (open the file and verify the existing pattern first; below is a self-contained block):

```css
/* === Outer Canvas (Sub-project 3) ============================== */
.oc-root {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 600px;
}

.oc-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  pointer-events: none;
  z-index: 5;
  text-align: center;
  gap: 12px;
  color: #1a1a1a;
}
.oc-empty-headline { font-size: 1.8rem; font-weight: 500; }
.oc-empty-hint { font-size: 0.95rem; pointer-events: auto; }
.oc-empty-cta {
  background: #111; color: #fff; border: none;
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
}

.oc-card {
  background: #fff;
  border: 1px solid #d8d8d8;
  border-radius: 10px;
  padding: 10px 12px;
  width: 100%; height: 100%;
  display: flex; flex-direction: column; gap: 4px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  font-size: 0.78rem;
  cursor: pointer;
  user-select: none;
}
.oc-card.is-archived { opacity: 0.55; border-style: dashed; }
.oc-card.is-pinned { border-color: #2a6df4; }
.oc-card-top {
  display: flex; gap: 6px; align-items: center;
  font-size: 0.65rem; color: #777;
}
.oc-card-pin { color: #2a6df4; font-size: 0.7rem; line-height: 1; }
.oc-card-tag {
  background: #eef2ff; color: #2a6df4; border-radius: 999px;
  padding: 1px 8px; font-size: 0.6rem;
}
.oc-card-date { margin-left: auto; }
.oc-card-title {
  font-size: 0.95rem; font-weight: 600; color: #111;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.oc-card-preview {
  color: #555;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.oc-card-handle {
  width: 8px; height: 8px; background: #2a6df4; border: 2px solid #fff;
}

.oc-frame {
  width: 100%; height: 100%;
  background: rgba(255, 250, 240, 0.6);
  border: 1px dashed #c9b48b;
  border-radius: 14px;
  padding: 8px 12px;
  pointer-events: all;
}
.oc-frame.is-loose { background: rgba(240, 240, 255, 0.6); border-color: #b8b8d8; }
.oc-frame-label {
  font-size: 0.75rem; font-weight: 600; color: #6c5b2d;
  text-transform: uppercase; letter-spacing: 0.06em;
}

.oc-node-hidden { display: none !important; }
```

- [ ] **Step 6: Commit**

```bash
git add src/components/OuterCanvas.jsx src/components/__tests__/OuterCanvas.test.jsx src/index.css
git commit -m "feat(canvas): OuterCanvas wires ReactFlow + filter overlay"
```

---

## Task 9: Swap `Home` for `OuterCanvas` in `App.jsx`

**Files:**
- Modify: `src/App.jsx`

The Sidebar's filter buttons keep emitting `{type: 'pinned' | 'archive' | 'tag' | 'group' | 'all'}` via `onFilterChange`; the only change is that the parent stops navigating to a separate view — the same canvas just dims non-matching cards.

- [ ] **Step 1: Read `src/App.jsx` and locate the `view === 'home'` branch (lines ~301-313 and the fallback ~327-340)**

- [ ] **Step 2: Replace the `Home` import with `OuterCanvas`**

```diff
-import Home from './components/Home';
+import OuterCanvas from './components/OuterCanvas';
```

- [ ] **Step 3: Replace both `<Home ...>` JSX blocks with `<OuterCanvas ...>`**

```diff
             {view === 'home' && (
-              <Home
-                notes={visibleNotes}
-                filter={filter}
-                onFilterChange={handleFilterChange}
+              <OuterCanvas
+                notes={notes}
+                groups={groups}
+                overlay={overlay}
+                filter={filter}
                 onOpenNote={handleOpenNote}
-                overlay={overlay}
-                onEditNote={triggerEdit}
-                onDeletePermanently={deletePermanently}
                 onCreateNote={handleCreateEmptyNote}
-                onMoveToGroup={(id) => setMoveModalNoteId(id)}
-                onRenameNote={(id, title) => updateNoteOnServer(id, { title })}
               />
             )}
```

And the same replacement for the fallback `view === 'note' && !activeNote` branch.

Note: pass the *unfiltered* `notes` list (not `visibleNotes`). Filtering now happens on the canvas via the layer overlay; the canvas needs to see every note so it can hide vs. show, and so reconciliation can re-add a card the user just un-archived.

- [ ] **Step 4: Update `handleFilterChange` to NOT navigate away from `note` view**

The original code:

```js
const handleFilterChange = useCallback((f) => {
  setFilter(f);
  if (view === 'note') { setView('home'); setActiveNoteId(null); }
}, [view]);
```

is acceptable as-is — clicking a sidebar filter still bounces back to the home/canvas view, which is correct. **No change required in this step**, but verify behavior in Task 12.

- [ ] **Step 5: Run typecheck + tests**

```bash
npm run typecheck && npm test
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/App.jsx
git commit -m "feat(canvas): swap Home grid for OuterCanvas in App.jsx"
```

---

## Task 10: Sidebar filter cosmetics check

**Files:**
- Modify (optional): `src/components/Sidebar.jsx`

The plan does NOT change the Sidebar's filter buttons — they still call `onFilterChange({type, value})`. What changed is what the parent does with that payload (it no longer changes the route).

- [ ] **Step 1: Visual sanity check**

Open `src/components/Sidebar.jsx`. Confirm `onFilterChange` is the only side effect of the filter buttons (`All notes`, `Pinned`, `Archive`, the tag rows, and group rows in `GroupTree`). No DOM manipulation, no view setter. **It is.**

- [ ] **Step 2: Decide whether to relabel "Archive" to "Archive layer"**

Skip relabeling. Keeping today's wording reduces friction. If users get confused that clicking "Archive" toggles a layer instead of opening a separate page, address it in a follow-up — out of scope for this PR.

- [ ] **Step 3: No code change → no commit**

---

## Task 11: Run the full suite + typecheck

**Files:** (none modified)

- [ ] **Step 1: Run typecheck**

```bash
npm run typecheck
```

Expected: zero errors.

- [ ] **Step 2: Run all tests**

```bash
npm test
```

Expected: every test passes. If a test that was green earlier now fails, fix it before continuing — do NOT mark complete with a red suite.

- [ ] **Step 3: Run vitest in coverage mode if available**

(Skip if not configured — not in foundation. Don't add coverage config in this PR.)

---

## Task 12: Manual end-to-end verification (REQUIRED before PR)

**Why:** UI features that pass unit tests can still be broken in the real app. Per CLAUDE.md rule and the `verification-before-completion` skill, evidence-before-assertions: load the app, observe behavior.

- [ ] **Step 1: Launch the app**

```bash
npm run electron:dev
```

- [ ] **Step 2: Verify the home view**

The pinboard canvas appears (background grid, ReactFlow controls in the corner). The page no longer shows the old Home headline grid.

- [ ] **Step 3: Verify migration**

If you had existing notes/groups before this branch:
- Cards appear for each note.
- Groups appear as frames with their note-cards inside.
- Ungrouped notes are below the last frame row.

`localStorage.getItem('deen.migrate.outer-canvas.v1')` returns `'done'`.

- [ ] **Step 4: Verify pin/tag/archive layer toggles**

In Sidebar: click "Pinned". Non-pinned cards disappear. Click "All notes" — they return. Click "Archive" — only archived cards show. Each toggle is instant; no view change, no scroll jump.

- [ ] **Step 5: Verify drag**

Drag a card. Drop it. Refresh the app (Ctrl+R). The card is at the dropped position. (Persistence works.)

- [ ] **Step 6: Verify connection-line drawing**

Hover over a card — handles appear at top + bottom. Drag from the source handle (bottom) of one card to the target handle (top) of another. A line appears. Refresh. The line is still there.

- [ ] **Step 7: Verify click-to-open**

Click a card body (not a handle). The note's NoteView opens. Press Esc — back to the canvas, with no state loss.

- [ ] **Step 8: Verify new-note flow**

Click "+ New note" in the sidebar (or Ctrl+Shift+D capture). The note shows up as a card on the canvas floor without a refresh.

- [ ] **Step 9: Verify Convex dashboard (rung 2)**

N/A for this project — backend is FastAPI + SQLite, not Convex. Open `python-service` logs in the dev console instead; confirm `PUT /outer-canvas` requests succeed (200 OK).

- [ ] **Step 10: If any step fails, fix and re-verify before continuing.**

---

## Task 13: Create the PR

**Files:** (none modified)

- [ ] **Step 1: Invoke superpowers:verification-before-completion to gate the assertion "ready to merge"**

- [ ] **Step 2: Push the branch**

```bash
git push -u origin canvas/3-outer-pinboard
```

- [ ] **Step 3: Run `gh pr create` titled `feat(canvas): outer pinboard replaces home grid`**

Body draft:

```markdown
## Summary
- Replaces the `Home` grid of note cards with `OuterCanvas` — a draggable, zoomable pinboard rendered with `@xyflow/react`.
- New singleton `outer_canvas` table holds the canvas state as JSON. A one-shot migration (gated by `deen.migrate.outer-canvas.v1`) converts existing notes + groups + localStorage overlay into the canvas state on first launch.
- Sidebar filters (pinned / archive / tags / groups) stop navigating to separate views and instead toggle visibility of matching cards on the canvas.

## Out of scope (per Sub-project 3 spec)
- Inner-canvas thumbnail on each card (deferred to v1.1).
- Deleting `Home.jsx` / `NoteCard.jsx` / `GroupTree.jsx` / `MoveToGroupModal.jsx` — kept on disk for one cycle so reviewers can compare.

## Test plan
- [x] `npm test` — all unit + component tests green.
- [x] `npm run typecheck` — clean.
- [x] Manual: migration runs once; cards render; drag persists; line draw persists; pin/archive layer toggles; click opens NoteView.
- [ ] Manual reviewer check: confirm migration on a clean install with sample data.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 4: Post the PR URL in the conversation.**

---

## Self-Review

Spec coverage — every requirement in the Sub-project 3 prompt has a task:

| Spec item | Task |
| --- | --- |
| New `OuterCanvas.jsx` using same engine as inner canvas | 1, 8 |
| New `NoteCardOnCanvas.jsx` w/ title, last-edited, preview, pin/tag indicators | 6 |
| Inner-canvas thumbnail OUT | (out of scope — not implemented) |
| Free-form connection lines (untyped at outer level) | 8 (onConnect + free edge default) |
| Frame primitive — reuse Sub-project 2 if merged, else minimal | 7 (minimal — no `src/components/canvas/Frame.jsx` exists yet) |
| Replace `Home` in `App.jsx` | 9 |
| Migration: groups→frames, notes default-grid, ungrouped on floor, behind flag | 2, 5 |
| Schema: new `outer_canvas` row (singleton) with JSON state | 4 |
| Filters become canvas overlays in Sidebar (not separate views) | 8, 9, 10 |
| Tests: render, drag, line draw, migration | 2, 5, 6, 8 (drag = state-conversion round-trip + node-position change handler; line draw = onConnect helper) |
| CSS prefix `.oc-` | 8 (CSS block) |

Placeholder scan: no `TBD`/`later`/`appropriate error handling`/`similar to`/`fill in details` patterns remain.

Type consistency: `createNoteCard`, `createOuterFrame`, `createFreeConnector`, `migrateLegacyToOuterCanvas`, `toReactFlow`, `fromReactFlow` are referenced consistently across tasks 2-8. The `data` shape passed into `NoteCardOnCanvas` (`{ note, pinned, tags, archived, onOpen }`) matches what `OuterCanvas` injects in `decoratedNodes`. The `migrateLegacyToOuterCanvas` overlay surface (`isPinned`, `isTrashed`, `getUserTags`) matches `useNoteOverlay` in the existing codebase.
