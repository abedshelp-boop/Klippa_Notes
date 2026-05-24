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
