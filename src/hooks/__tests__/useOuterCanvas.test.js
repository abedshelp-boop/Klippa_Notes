import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import useOuterCanvas from '../useOuterCanvas.js';

const MIGRATION_FLAG = 'deen.migrate.outer-canvas.v1';

function mockFetchSequence(responses) {
  const fn = vi.fn();
  responses.forEach((r) => {
    if (typeof r === 'function') fn.mockImplementationOnce(r);
    else fn.mockResolvedValueOnce({ ok: true, json: async () => r });
  });
  globalThis.fetch = fn;
  return fn;
}

function fakeOverlay(opts = {}) {
  return {
    isPinned: () => !!opts.pinned,
    isTrashed: () => !!opts.trashed,
    getUserTags: () => opts.tags || [],
  };
}

const isoNow = '2026-05-24T00:00:00Z';

describe('useOuterCanvas', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('on first load with no server state, runs migration and PUTs once', async () => {
    const notes = [{
      id: 'n1', title: 'A', group_id: null,
      created_at: isoNow, updated_at: isoNow,
    }];
    const fetchMock = mockFetchSequence([
      { state: null, updated_at: null },
      { state: {}, updated_at: '...' },
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes, groups: [], overlay: fakeOverlay() }));

    await waitFor(() => {
      expect(result.current.state).not.toBeNull();
      expect(result.current.state.noteCards).toHaveLength(1);
    });
    expect(localStorage.getItem(MIGRATION_FLAG)).toBe('done');
    const putCall = fetchMock.mock.calls
      .find(([, init]) => init?.method === 'PUT');
    expect(putCall).toBeDefined();
  });

  it('on second load with the flag set, does NOT re-run migration', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1,
      noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const fetchMock = mockFetchSequence([
      { state: existing, updated_at: '...' },
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes: [], groups: [], overlay: fakeOverlay() }));

    await waitFor(() => expect(result.current.state).not.toBeNull());
    const putCount = fetchMock.mock.calls
      .filter(([, init]) => init?.method === 'PUT').length;
    expect(putCount).toBe(0);
  });

  it('reconciles: a note not in state gets added to the canvas floor', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1, noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    mockFetchSequence([
      { state: existing, updated_at: '...' },
      { state: {}, updated_at: '...' },
    ]);

    const notes = [{
      id: 'new', title: 'fresh', group_id: null,
      created_at: isoNow, updated_at: isoNow,
    }];

    const { result } = renderHook(() =>
      useOuterCanvas({ notes, groups: [], overlay: fakeOverlay() }));

    await waitFor(() =>
      expect(result.current.state?.noteCards?.length).toBe(1));
    expect(result.current.state.noteCards[0].noteId).toBe('new');
  });

  it('reconciles: an orphan card (note no longer exists) is removed', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1,
      noteCards: [{
        id: 'ncard_keep', noteId: 'still-here',
        position: { x: 0, y: 0 }, size: { w: 240, h: 160 },
        rotation: 0, frameId: null, pinned: false, tags: [], archived: false,
      }, {
        id: 'ncard_gone', noteId: 'deleted',
        position: { x: 256, y: 0 }, size: { w: 240, h: 160 },
        rotation: 0, frameId: null, pinned: false, tags: [], archived: false,
      }],
      frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    mockFetchSequence([
      { state: existing, updated_at: '...' },
      { state: {}, updated_at: '...' },
    ]);
    const notes = [{
      id: 'still-here', title: 't', group_id: null,
      created_at: isoNow, updated_at: isoNow,
    }];

    const { result } = renderHook(() =>
      useOuterCanvas({ notes, groups: [], overlay: fakeOverlay() }));

    await waitFor(() =>
      expect(result.current.state?.noteCards.map((c) => c.noteId))
        .toEqual(['still-here']));
  });

  it('commit() PUTs the latest state', async () => {
    localStorage.setItem(MIGRATION_FLAG, 'done');
    const existing = {
      schemaVersion: 1, noteCards: [], frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const fetchMock = mockFetchSequence([
      { state: existing, updated_at: '...' },
      { state: {}, updated_at: '...' },
    ]);

    const { result } = renderHook(() =>
      useOuterCanvas({ notes: [], groups: [], overlay: fakeOverlay() }));
    await waitFor(() => expect(result.current.state).not.toBeNull());

    const next = {
      ...result.current.state,
      viewport: { x: 5, y: 5, zoom: 1.2 },
    };
    await act(async () => { await result.current.commit(next); });

    const putCalls = fetchMock.mock.calls
      .filter(([, init]) => init?.method === 'PUT');
    expect(putCalls.length).toBeGreaterThan(0);
    const body = JSON.parse(putCalls[putCalls.length - 1][1].body);
    expect(body.state.viewport).toEqual({ x: 5, y: 5, zoom: 1.2 });
  });
});
