import { describe, it, expect } from 'vitest';
import {
  createNoteCard,
  createOuterFrame,
  createFreeConnector,
  migrateLegacyToOuterCanvas,
  toReactFlow,
  fromReactFlow,
  matchesFilter,
} from '../outer.js';
import { emptyOuterCanvasState, isOuterCanvasState } from '../validators.js';

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
      noteId: 'n',
      position: { x: 100, y: 50 },
      size: { w: 320, h: 200 },
      pinned: true,
      tags: ['t'],
      archived: true,
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
    expect(f.size.h).toBeGreaterThan(0);
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
    const state = migrateLegacyToOuterCanvas({
      notes: [], groups: [], overlay: fakeOverlay(),
    });
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
    const state = migrateLegacyToOuterCanvas({
      notes: [], groups, overlay: fakeOverlay(),
    });
    expect(state.frames).toHaveLength(2);
    expect(state.frames.map((f) => f.label).sort()).toEqual(['Books', 'Recipes']);
    expect(state.frames.every((f) => !f.isAutoLooseIdeas)).toBe(true);
  });

  it("notes in a group land inside that group's frame", () => {
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
    const state = migrateLegacyToOuterCanvas({
      notes, groups: [], overlay: fakeOverlay(),
    });
    expect(state.noteCards).toHaveLength(1);
    expect(state.noteCards[0].frameId).toBeNull();
  });

  it('lays out cards in a grid inside each frame (no overlap)', () => {
    const groups = [{ id: 'g1', name: 'Books', parent_id: null }];
    const notes = Array.from({ length: 6 }, (_, i) => ({
      id: `n${i}`, title: `t${i}`, group_id: 'g1',
      created_at: isoNow, updated_at: isoNow,
    }));
    const state = migrateLegacyToOuterCanvas({ notes, groups, overlay: fakeOverlay() });
    const cards = state.noteCards;
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

describe('toReactFlow', () => {
  it('frames become frame-typed nodes; note cards become note-card nodes with parentId', () => {
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

  it('cards without a parent omit parentId', () => {
    const card = createNoteCard({ noteId: 'n1', frameId: null });
    const state = { ...emptyOuterCanvasState(), noteCards: [card] };
    const { nodes } = toReactFlow(state);
    expect(nodes[0].parentId).toBeUndefined();
    expect(nodes[0].extent).toBeUndefined();
  });

  it('free connectors become edges of type free', () => {
    const a = createNoteCard({ noteId: 'a' });
    const b = createNoteCard({ noteId: 'b' });
    const conn = createFreeConnector({ sourceCardId: a.id, targetCardId: b.id });
    const state = {
      ...emptyOuterCanvasState(),
      noteCards: [a, b],
      connectors: [conn],
    };
    const { edges } = toReactFlow(state);
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe(conn.id);
    expect(edges[0].source).toBe(a.id);
    expect(edges[0].target).toBe(b.id);
    expect(edges[0].type).toBe('free');
  });

  it('renders frames before note-cards so children draw on top', () => {
    const frame = createOuterFrame({ label: 'F' });
    const card = createNoteCard({ noteId: 'a', frameId: frame.id });
    const state = { ...emptyOuterCanvasState(), frames: [frame], noteCards: [card] };
    const { nodes } = toReactFlow(state);
    const frameIdx = nodes.findIndex((n) => n.id === frame.id);
    const cardIdx = nodes.findIndex((n) => n.id === card.id);
    expect(frameIdx).toBeLessThan(cardIdx);
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
    // parentId on the card node. Mimic that here.
    const cardNode = graph.nodes.find((n) => n.id === card.id);
    cardNode.parentId = frame.id;
    cardNode.extent = 'parent';
    const restored = fromReactFlow(graph, { x: 0, y: 0, zoom: 1 });
    expect(restored.noteCards[0].frameId).toBe(frame.id);
  });

  it('preserves card metadata across the round trip', () => {
    const card = createNoteCard({
      noteId: 'n', pinned: true, tags: ['a', 'b'], archived: true,
    });
    const state = { ...emptyOuterCanvasState(), noteCards: [card] };
    const restored = fromReactFlow(toReactFlow(state), state.viewport);
    expect(restored.noteCards[0].pinned).toBe(true);
    expect(restored.noteCards[0].tags).toEqual(['a', 'b']);
    expect(restored.noteCards[0].archived).toBe(true);
  });

  it('produces a valid OuterCanvasState (passes the validator)', () => {
    const empty = toReactFlow(emptyOuterCanvasState());
    const restored = fromReactFlow(empty, { x: 0, y: 0, zoom: 1 });
    expect(isOuterCanvasState(restored)).toBe(true);
  });
});

describe('matchesFilter', () => {
  const baseCard = {
    pinned: false, tags: [], archived: false, frameId: null,
  };

  it('all: shows non-archived, hides archived', () => {
    expect(matchesFilter(baseCard, { type: 'all' })).toBe(true);
    expect(matchesFilter({ ...baseCard, archived: true }, { type: 'all' }))
      .toBe(false);
  });

  it('pinned: only pinned non-archived cards', () => {
    expect(matchesFilter({ ...baseCard, pinned: true }, { type: 'pinned' }))
      .toBe(true);
    expect(matchesFilter(baseCard, { type: 'pinned' })).toBe(false);
    expect(matchesFilter(
      { ...baseCard, pinned: true, archived: true }, { type: 'pinned' }
    )).toBe(false);
  });

  it('archive: only archived cards', () => {
    expect(matchesFilter({ ...baseCard, archived: true }, { type: 'archive' }))
      .toBe(true);
    expect(matchesFilter(baseCard, { type: 'archive' })).toBe(false);
  });

  it('tag: matches the named tag, ignores archived', () => {
    const card = { ...baseCard, tags: ['focus', 'urgent'] };
    expect(matchesFilter(card, { type: 'tag', value: 'focus' })).toBe(true);
    expect(matchesFilter(card, { type: 'tag', value: 'missing' })).toBe(false);
    expect(matchesFilter(
      { ...card, archived: true }, { type: 'tag', value: 'focus' }
    )).toBe(false);
  });

  it('group: matches the named frame', () => {
    expect(matchesFilter(
      { ...baseCard, frameId: 'frame_a' },
      { type: 'group', value: 'frame_a' },
    )).toBe(true);
    expect(matchesFilter(
      { ...baseCard, frameId: 'frame_a' },
      { type: 'group', value: 'frame_b' },
    )).toBe(false);
  });

  it('null/undefined filter behaves like "all"', () => {
    expect(matchesFilter(baseCard, null)).toBe(true);
    expect(matchesFilter(baseCard, undefined)).toBe(true);
  });
});
