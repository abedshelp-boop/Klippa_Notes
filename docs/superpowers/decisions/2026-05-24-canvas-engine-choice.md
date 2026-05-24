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

See [experiments/canvas-engine-spike/](../../../experiments/canvas-engine-spike/) — both 30-line POCs are committed so the comparison stays auditable.

## What sub-projects do with this

- Sub-project 1: `npm install @xyflow/react` and build `src/components/InnerCanvas.jsx` against React Flow.
- Sub-project 2: Register custom node types for Frame, MediaCard, LinkCard; custom edge types for the five connector types.
- Sub-project 3: Reuse the same engine for the outer pinboard (`OuterCanvas.jsx`). One engine across both levels.
- Sub-project 6: Serialize node + edge state as the canvas snapshot fed to Sonnet 4.5.

## Reversal cost (if we have to switch later)

Moderate. The state model (in `src/lib/types.js` from this foundation PR) is engine-agnostic — `Card`, `Frame`, `Connector` types don't reference React Flow internals. The render layer would need to be rewritten in each sub-project's component files; state migration is free.
