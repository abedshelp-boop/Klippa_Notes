---
title: Canvas Sub-project 1 — Inner Canvas Foundation
date: 2026-05-25
status: ready
spec: docs/superpowers/specs/2026-05-24-canvas-redesign-design.md
foundation: tag canvas-foundation-v1
workflow: main-only (no branches, no PRs, no worktrees)
---

# Canvas Sub-project 1 — Inner Canvas Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Main-only workflow — commit per task on main, push when verification completes.

**Goal:** Replace the document-style `NoteView` with an inner-canvas view holding ONE draggable, editable text-card primitive per note. After this ships, opening a note shows that note's markdown inside a single TextCard on a React Flow canvas. Mermaid, charts, KaTeX, and syntax highlighting work identically inside the card.

**Architecture:** React Flow (`@xyflow/react` v12, MIT) — chosen in foundation. One custom node type, `text`, rendered by `TextCard.jsx`. Position, size, rotation, markdown live in `notes.canvas_state` (new nullable JSON column). When null, renderer derives a one-TextCard state from legacy `notes.content` on the fly (lossless); a one-time migration backfills the column on first launch. Markdown render pipeline is copied verbatim from `NoteView.jsx` into `TextCard.jsx` so the existing 5-plugin + custom-code-component setup is preserved exactly. State transforms live in `src/lib/canvas/cardState.js` as pure functions so they're testable in vitest's existing `node` env without jsdom or @testing-library.

**Tech Stack:** React 19 · `@xyflow/react` v12 · existing react-markdown + remark-gfm + remark-math + rehype-katex + rehype-highlight + rehype-raw + rehype-sanitize · Vitest (node env) · `react-dom/server` for shape-of-render assertions · aiosqlite migration.

---

## File map

**Create:**
- `src/components/InnerCanvas.jsx` — rail (back/title/pin/archive/date) + React Flow surface + transitional dictation panel lifted unchanged from NoteView.
- `src/components/cards/TextCard.jsx` — custom node. Display = rendered markdown. Edit = textarea. Double-click to edit, Ctrl+Enter to commit, Esc to cancel.
- `src/lib/canvas/cardState.js` — pure functions: `innerStateFromNote`, `applyTextEdit`, `applyNodePosition`, `stateToReactFlowNodes`.
- `src/components/cards/__tests__/TextCard.test.jsx`
- `src/components/__tests__/InnerCanvas.test.jsx`
- `src/lib/canvas/__tests__/cardState.test.js`

**Modify:**
- `src/lib/canvas/migrate.js` — add `migrateLegacyMarkdown(noteContent)`.
- `src/lib/canvas/__tests__/migrate.test.js` — add idempotency tests.
- `src/App.jsx` — swap `<NoteView>` for `<InnerCanvas>`, add `deen.migrate.canvas.v1` useEffect.
- `src/index.css` — add `.ic-*` namespaced styles.
- `python-service/database.py` — add `canvas_state` column migration; auto-parse in `_row_to_dict`; accept in `update_note`.
- `python-service/routes.py` — accept `canvas_state` in PUT `/notes/{id}`.
- `package.json` + `package-lock.json` — add `@xyflow/react`.

**Untouched (dead, deleted by later sub-project):** `src/components/NoteView.jsx`.

---

## Task 1: Python schema migration — add canvas_state column

**Files:** `python-service/database.py`, `python-service/routes.py`

- [ ] **1.1 Migration block in `init_db()`** — after the `group_id` migration, add:

```python
        if "canvas_state" not in columns:
            await db.execute(
                "ALTER TABLE notes ADD COLUMN canvas_state TEXT"
            )
```

- [ ] **1.2 Parse `canvas_state` in `_row_to_dict()`** — after the existing tags parse:

```python
    raw_cs = d.get("canvas_state")
    if raw_cs is None:
        d["canvas_state"] = None
    else:
        try:
            d["canvas_state"] = json.loads(raw_cs)
        except (json.JSONDecodeError, TypeError):
            d["canvas_state"] = None
```

- [ ] **1.3 Accept `canvas_state` in `update_note()`** — add a kwarg + branch (see code block below). New signature accepts `canvas_state=_UNSET`; branch JSON-encodes dicts and passes strings through.

```python
    if canvas_state is not _UNSET:
        fields.append("canvas_state = ?")
        if canvas_state is None:
            values.append(None)
        elif isinstance(canvas_state, str):
            values.append(canvas_state)
        else:
            values.append(json.dumps(canvas_state))
```

- [ ] **1.4 Accept `canvas_state` in routes.py `update_note_route()`** — add to the existing `kwargs` dict mapping:

```python
    if "canvas_state" in body:
        kwargs["canvas_state"] = body["canvas_state"]
```

- [ ] **1.5 Smoke pytest** — `cd python-service && python -m pytest -q`. Expected: existing canary passes.

- [ ] **1.6 Commit** —

```
feat(canvas): add canvas_state column + PUT support

Nullable TEXT column on notes; null on the wire means "render the
legacy content as a single TextCard" (sub-project 1 fallback). PUT
/notes/{id} now accepts canvas_state; _row_to_dict parses it the
same way tags are handled.
```

---

## Task 2: `migrateLegacyMarkdown` + pure state-transform helpers

**Files:** create `src/lib/canvas/cardState.js`; create `src/lib/canvas/__tests__/cardState.test.js`; modify `src/lib/canvas/migrate.js` and its test.

- [ ] **2.1 Write failing test** — `src/lib/canvas/__tests__/cardState.test.js`. Tests: `innerStateFromNote` (4 cases incl. null content, valid canvas_state passthrough, invalid canvas_state falls back), `applyTextEdit` (updates target, ignores unknown id, immutable, preserves position/size/rotation/frameId), `applyNodePosition` (updates target, ignores unknown id, immutable, preserves markdown), `stateToReactFlowNodes` (1:1 mapping, empty state → empty array).

- [ ] **2.2 Run** — `npm test -- src/lib/canvas/__tests__/cardState.test.js` → FAIL (module not found).

- [ ] **2.3 Implement `cardState.js`** — 4 pure functions, default text-card size `{w:640,h:360}`, uses `cardId()` from `ids.js` and `isInnerCanvasState`/`emptyInnerCanvasState` from `validators.js`.

- [ ] **2.4 Run** — PASS.

- [ ] **2.5 Add `migrateLegacyMarkdown` to `migrate.js`** — delegates to `innerStateFromNote({content: noteContent ?? ''})`. Update import in `migrate.test.js`. Add idempotency test: `migrateInnerCanvasState(migrateLegacyMarkdown(x)) === migrateLegacyMarkdown(x)`.

- [ ] **2.6 Run** — `npm test -- src/lib/canvas` → all pass.

- [ ] **2.7 Commit** —

```
feat(canvas): cardState pure functions + migrateLegacyMarkdown

innerStateFromNote, applyTextEdit, applyNodePosition,
stateToReactFlowNodes — all pure, immutable, exhaustively tested
in vitest's node env. migrateLegacyMarkdown delegates and is
idempotent through migrateInnerCanvasState (spec requirement).
```

---

## Task 3: Install `@xyflow/react`

- [ ] **3.1** `npm install @xyflow/react`. Verify v12+: `node -e "console.log(require('./package.json').dependencies['@xyflow/react'])"`. If v11 installed, force `npm install @xyflow/react@^12`.
- [ ] **3.2** `npm test` — all prior tests still pass.
- [ ] **3.3 Commit** — `chore(deps): add @xyflow/react for canvas surface`

---

## Task 4: `TextCard.jsx` — render markdown + edit toggle

**Files:** create `src/components/cards/TextCard.jsx`; create `src/components/cards/__tests__/TextCard.test.jsx`.

- [ ] **4.1 Write failing test** using `renderToStaticMarkup` from `react-dom/server`. Cases: renders `<h1>` for `# Hello`, renders empty card without crashing, applies `.ic-textcard` class, renders fenced code as `<code>`. All tests pass `isPreview` prop to bypass `<Handle>` (which needs `ReactFlowProvider` context).

- [ ] **4.2 Run** → FAIL (module not found).

- [ ] **4.3 Implement `TextCard.jsx`** — copy `SANITIZE_SCHEMA` + plugin arrays + `components.code` override verbatim from `NoteView.jsx` (lines ~35-60 + ~593-610). Imports: react, react-markdown, remark-gfm, remark-math, rehype-katex, rehype-highlight, rehype-raw, rehype-sanitize, `{Handle, Position}` from @xyflow/react, MermaidBlock, ChartBlock. Props: `id`, `data: {markdown}`, `onCommitMarkdown`, `onEditingChange`, `isPreview=false`. State machine: display↔edit, double-click to enter, blur or Ctrl+Enter to commit, Esc to cancel, textarea auto-resizes. Stop drag-event propagation on textarea (`onMouseDown={(e) => e.stopPropagation()}`).

- [ ] **4.4 Run** → PASS.

- [ ] **4.5 Commit** —

```
feat(canvas): TextCard component — markdown render + edit toggle

Preserves react-markdown pipeline verbatim from NoteView (mermaid +
chart + KaTeX + SVG-allowing sanitize schema). Display mode renders
markdown; double-click → textarea. Commit on blur/Ctrl+Enter, cancel
on Esc. isPreview skips Handle wiring for test rendering outside a
ReactFlowProvider.
```

---

## Task 5: `InnerCanvas.jsx` — orchestrate a single TextCard

**Files:** create `src/components/InnerCanvas.jsx`; create `src/components/__tests__/InnerCanvas.test.jsx`.

- [ ] **5.1 Write failing test** using `renderToStaticMarkup` + `previewMode` prop. Cases: renders title in rail, renders legacy content as TextCard when `canvas_state` null, uses `canvas_state` when valid (legacy content ignored), `note=null` → empty string.

- [ ] **5.2 Run** → FAIL.

- [ ] **5.3 Implement `InnerCanvas.jsx`** —
  - Lifts rail (back/title/pin/archive/date), tags editor, and dictation panel from NoteView unchanged (note-level concerns, sub-project 4 will redesign dictation).
  - State: `useState(() => innerStateFromNote(note))`. Re-derives on `note?.id/canvas_state/content` change.
  - `NODE_TYPES = {text: TextCard}` declared module-level (stable identity, performance-critical for React Flow).
  - `handleNodesChange`: applies RF changes to local state via `applyNodeChanges` + `applyNodePosition` for each moved card; schedules 600ms-debounced save via `onUpdateNote(id, {canvas_state})`.
  - `handleCommitMarkdown(cardId, markdown)`: `applyTextEdit` + scheduleSave.
  - `handleEditingChange(cardId, isEditing)`: tracks in ref so `nodes` map can flip `draggable` off while editing.
  - `nodes` derived via `useMemo(() => stateToReactFlowNodes(canvasState).map(injecting callbacks + draggable flag))`.
  - `previewMode` branch: skips `<ReactFlow>` entirely, renders cards in a static `.ic-canvas-preview` div using `<TextCard isPreview />`. Production always `previewMode={false}`.
  - Production branch: `<ReactFlowProvider><ReactFlow nodes={nodes} edges={[]} onNodesChange={handleNodesChange} nodeTypes={NODE_TYPES} fitView nodesConnectable={false} proOptions={{hideAttribution: true}}><Background gap={16}/><Controls showInteractive={false}/></ReactFlow></ReactFlowProvider>`.
  - Import `@xyflow/react/dist/style.css` at top.
  - Cleanup save timer on unmount.

- [ ] **5.4 Run** → all four cases PASS.

- [ ] **5.5 Commit** —

```
feat(canvas): InnerCanvas component renders a single TextCard

Reads canvas_state when valid, falls back to a one-TextCard derived
from note.content otherwise (lossless fallback so unmigrated notes
still render). Writes via debounced onUpdateNote(id, {canvas_state}).
Dictation panel + title editing lifted unchanged from NoteView; the
dictation flow is transitional — sub-project 4 redesigns it.
```

---

## Task 6: CSS — `.ic-*` namespaced styles

**Files:** modify `src/index.css`

- [ ] **6.1** Insert `.ic-*` block AFTER the existing `.note-view*` block. Includes: `.ic-note-view` (flex column), `.ic-rail` (top bar), `.ic-back/ic-rail-spacer/ic-rail-date/ic-rail-actions`, `.ic-header/ic-title/ic-title-input/ic-tags/ic-dictation`, `.ic-surface` (dot-grid background), `.ic-canvas-preview` (vertical layout for test/thumbnail mode), `.ic-textcard/ic-textcard-body/ic-textcard-editor` (the card itself), plus `.ic-surface .react-flow__node {padding:0; border:none; background:transparent; width:auto;}` and `.ic-surface .react-flow__handle {opacity:0; pointer-events:none;}` to neutralize React Flow's default node chrome.
- [ ] **6.2 Verify** — `grep -c "\.ic-" src/index.css` ≥ 15.
- [ ] **6.3 Commit** — `style(canvas): ic-* namespaced styles for inner canvas + TextCard`

---

## Task 7: `App.jsx` — swap component + add migration effect

**Files:** modify `src/App.jsx`

- [ ] **7.1** Swap line 6 import: `NoteView` → `InnerCanvas`.
- [ ] **7.2** Swap JSX usage (lines ~315-326) `<NoteView ... />` → `<InnerCanvas ... />`. Props are 1:1 compatible.
- [ ] **7.3** Add a new `useEffect` after the existing `deen.migrate.titles.v1` block, gated by `deen.migrate.canvas.v1`. Lazy-imports `migrateLegacyMarkdown` from `./lib/canvas/migrate.js`, iterates `notes`, skips any with `canvas_state != null`, PUTs `{canvas_state: migrateLegacyMarkdown(note.content || '')}` to each, sets the flag when complete. Dependency array `[notes.length, updateNoteOnServer]` so we don't re-run on every WS update.
- [ ] **7.4** `npm test` — every prior test still passes.
- [ ] **7.5** `npm run typecheck` — no new errors in canvas files.
- [ ] **7.6 Commit** —

```
feat(canvas): swap NoteView for InnerCanvas + backfill migration

Opening a note now mounts InnerCanvas. New useEffect backfills
canvas_state for every existing note on first launch, gated by
deen.migrate.canvas.v1 — same pattern as the titleOverride drain.
```

---

## Task 8: End-to-end verification + push

- [ ] **8.1** `npm test` — every test passes.
- [ ] **8.2** `npm run typecheck` — no new errors.
- [ ] **8.3** `cd python-service && python -m pytest -q` — pytest canary passes.
- [ ] **8.4** Manual smoke: `npm run electron:dev`, open an existing note, drag card, double-click + edit + Ctrl+Enter, reopen note (state persists), test a note with mermaid + chart + KaTeX blocks (render identical to before), check DevTools console (no errors). Open `klippa.db` with sqlite3: `SELECT id, canvas_state FROM notes LIMIT 5;` → JSON for migrated notes.
- [ ] **8.5** `git push origin main` — push the 7 commits.

---

## Spec coverage

| Requirement | Task |
|---|---|
| InnerCanvas.jsx using chosen engine | 5 |
| TextCard.jsx with existing markdown pipeline | 4 |
| Preserve mermaid + chart + KaTeX | 4 (verbatim copy) + 8.4 smoke |
| Replace NoteView in App.jsx | 7 |
| Lossless migration in migrate.js + localStorage flag | 2 + 7 |
| Schema change: canvas_state column, null → fallback | 1 |
| Tests: per-card render, drag, edit-commit, migration idempotency | 4 (render), 5 (edit-commit), 2 (drag-as-position-change + idempotency) |
| `.ic-` CSS namespace | 6 |

## Risks

1. **React 19 / @xyflow/react v12 compat** — verified during install (Task 3).
2. **`<Handle>` context** — TextCard requires `ReactFlowProvider` in production; tests use `isPreview`.
3. **CSS** — all new classes prefixed `.ic-`. Dictation classes (`.dictation-*`) reused intentionally from NoteView's still-present-but-unused styles.
4. **Debounced save vs. quit** — 600ms window of potential loss; acceptable for v1.
5. **DB migration on running dev process** — brief lock; relaunch python service if it hangs.
