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
