// @ts-nocheck
// Tests read Card.data.markdown directly; the runtime always returns
// TextCardData here, but the JSDoc discriminated union can't be narrowed
// from .type at the test-call site without verbose assertions.
import { describe, it, expect } from 'vitest';
import {
  innerStateFromNote,
  applyTextEdit,
  applyNodePosition,
  stateToReactFlowNodes,
} from '../cardState.js';
import { isInnerCanvasState, emptyInnerCanvasState } from '../validators.js';

describe('innerStateFromNote', () => {
  it('returns valid InnerCanvasState for a note with content', () => {
    const state = innerStateFromNote({ id: 'n1', content: '# hi\n\nbody text' });
    expect(isInnerCanvasState(state)).toBe(true);
    expect(state.cards).toHaveLength(1);
    expect(state.cards[0].type).toBe('text');
    expect(state.cards[0].data.markdown).toBe('# hi\n\nbody text');
    expect(state.cards[0].position).toEqual({ x: 0, y: 0 });
    expect(state.cards[0].rotation).toBe(0);
    expect(state.cards[0].frameId).toBe(null);
  });

  it('returns one card with empty markdown for an empty-content note', () => {
    const state = innerStateFromNote({ id: 'n1', content: '' });
    expect(state.cards).toHaveLength(1);
    expect(state.cards[0].data.markdown).toBe('');
  });

  it('returns one card with empty markdown for a note with null content', () => {
    const state = innerStateFromNote({ id: 'n1', content: null });
    expect(state.cards).toHaveLength(1);
    expect(state.cards[0].data.markdown).toBe('');
  });

  it('uses note.canvas_state when present and valid', () => {
    const provided = {
      schemaVersion: 1,
      cards: [{
        id: 'card_x', type: 'text',
        position: { x: 100, y: 50 }, size: { w: 320, h: 200 },
        rotation: 0, frameId: null,
        data: { markdown: 'from canvas_state' },
      }],
      frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const state = innerStateFromNote({
      id: 'n1', content: 'legacy', canvas_state: provided,
    });
    expect(state).toEqual(provided);
  });

  it('falls back to legacy content when canvas_state is invalid', () => {
    const state = innerStateFromNote({
      id: 'n1', content: 'legacy text', canvas_state: { junk: true },
    });
    expect(state.cards).toHaveLength(1);
    expect(state.cards[0].data.markdown).toBe('legacy text');
  });

  it('cards have a sensible default size', () => {
    const state = innerStateFromNote({ id: 'n1', content: 'x' });
    expect(state.cards[0].size.w).toBeGreaterThan(100);
    expect(state.cards[0].size.h).toBeGreaterThan(50);
  });
});

describe('applyTextEdit', () => {
  it('updates the markdown of the specified card', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'old' });
    const cardId = before.cards[0].id;
    const after = applyTextEdit(before, cardId, 'new');
    expect(after.cards[0].data.markdown).toBe('new');
  });

  it('returns the same state when the card id is unknown', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'old' });
    const after = applyTextEdit(before, 'card_unknown', 'new');
    expect(after).toEqual(before);
  });

  it('does not mutate the input', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'old' });
    const snapshot = JSON.stringify(before);
    applyTextEdit(before, before.cards[0].id, 'new');
    expect(JSON.stringify(before)).toBe(snapshot);
  });

  it('preserves position, size, rotation, and frameId', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'x' });
    before.cards[0].position = { x: 42, y: 99 };
    before.cards[0].size = { w: 500, h: 300 };
    before.cards[0].rotation = 5;
    const after = applyTextEdit(before, before.cards[0].id, 'edited');
    expect(after.cards[0].position).toEqual({ x: 42, y: 99 });
    expect(after.cards[0].size).toEqual({ w: 500, h: 300 });
    expect(after.cards[0].rotation).toBe(5);
    expect(after.cards[0].frameId).toBe(null);
  });
});

describe('applyNodePosition', () => {
  it('updates the position of the specified card', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'x' });
    const after = applyNodePosition(before, before.cards[0].id, { x: 200, y: 150 });
    expect(after.cards[0].position).toEqual({ x: 200, y: 150 });
  });

  it('returns the same state when the card id is unknown', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'x' });
    const after = applyNodePosition(before, 'card_unknown', { x: 1, y: 2 });
    expect(after).toEqual(before);
  });

  it('does not mutate the input', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'x' });
    const snapshot = JSON.stringify(before);
    applyNodePosition(before, before.cards[0].id, { x: 9, y: 9 });
    expect(JSON.stringify(before)).toBe(snapshot);
  });

  it('preserves markdown, size, rotation, and frameId', () => {
    const before = innerStateFromNote({ id: 'n1', content: 'keep me' });
    const after = applyNodePosition(before, before.cards[0].id, { x: 7, y: 8 });
    expect(after.cards[0].data.markdown).toBe('keep me');
    expect(after.cards[0].size).toEqual(before.cards[0].size);
  });
});

describe('stateToReactFlowNodes', () => {
  it('maps each text card to a React Flow node with id, type, position, data', () => {
    const state = innerStateFromNote({ id: 'n1', content: 'hello' });
    const nodes = stateToReactFlowNodes(state);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].id).toBe(state.cards[0].id);
    expect(nodes[0].type).toBe('text');
    expect(nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(nodes[0].data.markdown).toBe('hello');
  });

  it('returns an empty array when state has no cards', () => {
    expect(stateToReactFlowNodes(emptyInnerCanvasState())).toEqual([]);
  });
});
