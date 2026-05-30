// @ts-check
/**
 * Canvas state migration. Sub-project 1 ships `migrateLegacyMarkdown`,
 * which converts a pre-redesign note's `content` field into a one-TextCard
 * `InnerCanvasState`. App.jsx's migration block calls this once per note
 * on first launch, gated by the `deen.migrate.canvas.v1` localStorage flag.
 *
 * @module
 */

import { isInnerCanvasState, emptyInnerCanvasState } from './validators.js';
import { innerStateFromNote } from './cardState.js';

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

/**
 * One-time migration: convert a legacy note's markdown content into a
 * one-TextCard InnerCanvasState at position (0,0). Idempotent under
 * `migrateInnerCanvasState` — the output already satisfies isInnerCanvasState.
 *
 * Null / undefined / non-string input is treated as an empty card so callers
 * don't have to coalesce. App.jsx iterates every note and PUTs the result
 * to `/notes/{id}` as `canvas_state`.
 *
 * @param {string | null | undefined} noteContent
 * @returns {import('../types.js').InnerCanvasState}
 */
export function migrateLegacyMarkdown(noteContent) {
  return innerStateFromNote({ content: noteContent ?? '' });
}
