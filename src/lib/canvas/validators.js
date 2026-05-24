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
