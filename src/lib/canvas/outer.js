// @ts-check
/**
 * Pure helpers for the outer pinboard canvas. No React, no fetch, no IPC.
 * All ids come from src/lib/canvas/ids.js. All shapes come from src/lib/types.js.
 *
 * Two responsibilities live here:
 *   1) Factories + one-shot legacy-data migration to OuterCanvasState.
 *   2) Bidirectional conversion between OuterCanvasState and the
 *      `{ nodes, edges }` shape React Flow expects.
 */

import { noteCardId, frameId, connectorId } from './ids.js';
import { emptyOuterCanvasState } from './validators.js';

const DEFAULT_NOTE_CARD_SIZE = { w: 240, h: 160 };
const DEFAULT_FRAME_SIZE = { w: 1200, h: 600 };
const FRAME_GAP = 80;
// y leaves room for the label bar
const FRAME_INNER_PAD = { x: 24, y: 60 };
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
 * One-time migration of pre-canvas state into an OuterCanvasState. Pure —
 * depends only on its arguments.
 *
 * Group order is preserved as given (caller typically already sorts by name).
 * Notes inside a group are arranged in a row-major grid inside their frame.
 * Ungrouped notes sit on the canvas floor in a wider row-major grid below
 * the last frame row.
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

  /** @type {Map<string, import('../types.js').Frame>} */
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

  /** @type {Map<string, import('../types.js').NoteCard[]>} */
  const grouped = new Map();
  /** @type {import('../types.js').NoteCard[]} */
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
      const list = grouped.get(frame.id);
      if (list) list.push(card);
      else grouped.set(frame.id, [card]);
    } else {
      ungrouped.push(card);
    }
  }

  for (const frame of state.frames) {
    const cards = grouped.get(frame.id) || [];
    const innerW = frame.size.w - FRAME_INNER_PAD.x * 2;
    const cardsPerRow = Math.max(
      1,
      Math.floor((innerW + CARD_GAP) / (DEFAULT_NOTE_CARD_SIZE.w + CARD_GAP)),
    );
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
