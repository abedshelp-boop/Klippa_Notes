// @ts-check
/**
 * Pure-function helpers for inner canvas state. These keep all the
 * data transforms out of the React tree so they can be exhaustively
 * unit-tested in vitest's node environment, with no DOM dependency
 * and no @testing-library setup.
 *
 * Every function returns a new InnerCanvasState — never mutates the
 * input. The source of truth for canvas data is the JSON blob in
 * notes.canvas_state; these helpers translate to/from React Flow's
 * nodes array and apply edits.
 */

import { cardId } from './ids.js';
import { isInnerCanvasState, emptyInnerCanvasState } from './validators.js';

const DEFAULT_TEXT_CARD_SIZE = { w: 640, h: 360 };

/**
 * Derive an InnerCanvasState for rendering a note. Precedence:
 *   1. If note.canvas_state is a valid InnerCanvasState, use it as-is.
 *   2. Otherwise build a one-TextCard state at (0,0) holding note.content.
 *
 * This is the read-side fallback that lets a note render even when the
 * one-time migration hasn't backfilled canvas_state yet. The migration
 * (see migrate.js > migrateLegacyMarkdown) writes the same shape this
 * function produces, so the post-migration shape is identical to the
 * pre-migration render.
 *
 * @param {{ id?: string, content?: string | null, canvas_state?: unknown }} note
 * @returns {import('../types.js').InnerCanvasState}
 */
export function innerStateFromNote(note) {
  if (note && isInnerCanvasState(note.canvas_state)) {
    return /** @type {import('../types.js').InnerCanvasState} */ (note.canvas_state);
  }
  const markdown = (note && typeof note.content === 'string') ? note.content : '';
  return {
    schemaVersion: 1,
    cards: [{
      id: cardId(),
      type: 'text',
      position: { x: 0, y: 0 },
      size: { ...DEFAULT_TEXT_CARD_SIZE },
      rotation: 0,
      frameId: null,
      data: { markdown },
    }],
    frames: [],
    connectors: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
}

/**
 * Replace the markdown of a single text card. Returns the state unchanged
 * if the card id is unknown or the target card is not type 'text'.
 *
 * @param {import('../types.js').InnerCanvasState} state
 * @param {string} targetCardId
 * @param {string} markdown
 * @returns {import('../types.js').InnerCanvasState}
 */
export function applyTextEdit(state, targetCardId, markdown) {
  const idx = state.cards.findIndex((c) => c.id === targetCardId);
  if (idx === -1) return state;
  const card = state.cards[idx];
  if (card.type !== 'text') return state;
  const nextCard = {
    ...card,
    data: { ...card.data, markdown },
  };
  const nextCards = state.cards.slice();
  nextCards[idx] = nextCard;
  return { ...state, cards: nextCards };
}

/**
 * Move a card to a new canvas position. Returns the state unchanged
 * if the card id is unknown.
 *
 * @param {import('../types.js').InnerCanvasState} state
 * @param {string} targetCardId
 * @param {{ x: number, y: number }} position
 * @returns {import('../types.js').InnerCanvasState}
 */
export function applyNodePosition(state, targetCardId, position) {
  const idx = state.cards.findIndex((c) => c.id === targetCardId);
  if (idx === -1) return state;
  const card = state.cards[idx];
  const nextCard = {
    ...card,
    position: { x: position.x, y: position.y },
  };
  const nextCards = state.cards.slice();
  nextCards[idx] = nextCard;
  return { ...state, cards: nextCards };
}

/**
 * Convert an InnerCanvasState into a React Flow `nodes` array. Each
 * Card becomes one node; the consumer registers a `nodeTypes` map
 * keyed by Card.type that React Flow uses to pick the renderer.
 *
 * @param {import('../types.js').InnerCanvasState} state
 * @returns {Array<{ id: string, type: string, position: { x: number, y: number }, data: object, style?: object }>}
 */
export function stateToReactFlowNodes(state) {
  if (!state || !Array.isArray(state.cards)) return [];
  return state.cards.map((card) => ({
    id: card.id,
    type: card.type,
    position: card.position,
    data: card.data,
    style: { width: card.size.w, height: card.size.h },
  }));
}

// Re-export empty state so the InnerCanvas component can import a single
// module for everything state-related.
export { emptyInnerCanvasState };
