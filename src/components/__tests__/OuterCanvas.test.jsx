import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import OuterCanvas from '../OuterCanvas.jsx';

function fakeOverlay(opts = {}) {
  return {
    isPinned: (id) => (opts.pinnedIds || []).includes(id),
    isTrashed: (id) => (opts.trashedIds || []).includes(id),
    getUserTags: (id) => (opts.tagMap || {})[id] || [],
  };
}

function mockFetchSequence(responses) {
  const fn = vi.fn();
  responses.forEach((r) => {
    fn.mockResolvedValueOnce({ ok: true, json: async () => r });
  });
  globalThis.fetch = fn;
  return fn;
}

const isoNow = '2026-05-24T00:00:00Z';

describe('OuterCanvas', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders an empty state CTA when no notes', async () => {
    mockFetchSequence([
      { state: null, updated_at: null },
      { state: {}, updated_at: '...' },
    ]);
    render(
      <OuterCanvas
        notes={[]} groups={[]} overlay={fakeOverlay()}
        filter={{ type: 'all' }}
        onOpenNote={() => {}} onCreateNote={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText(/Nothing here yet/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/Hey Deen/i)).toBeInTheDocument();
  });

  it('renders a note card after migration', async () => {
    mockFetchSequence([
      { state: null, updated_at: null },
      { state: {}, updated_at: '...' },
    ]);
    const notes = [{
      id: 'n1', title: 'A test note', content: 'preview text', group_id: null,
      created_at: isoNow, updated_at: isoNow,
    }];
    render(
      <OuterCanvas
        notes={notes} groups={[]} overlay={fakeOverlay()}
        filter={{ type: 'all' }} onOpenNote={() => {}}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText('A test note')).toBeInTheDocument(),
    );
  });

  it('renders without crashing for each filter shape', async () => {
    // React Flow's measurement layer is unreliable in jsdom — the
    // class-on-node / DOM visibility assertion is a manual verification
    // step (Plan Task 12 step 4). Here we verify the canvas mounts and
    // unmounts cleanly for every filter shape. The pure-function
    // `matchesFilter` logic is covered by unit tests in
    // lib/canvas/__tests__/outer.test.js.
    const state = {
      schemaVersion: 1,
      noteCards: [
        { id: 'ncard_a', noteId: 'n1', position: { x: 0, y: 0 },
          size: { w: 240, h: 160 }, rotation: 0, frameId: null,
          pinned: true, tags: ['x'], archived: false },
      ],
      frames: [], connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    const notes = [{
      id: 'n1', title: 'one', content: '', updated_at: isoNow,
    }];

    for (const filter of [
      { type: 'all' },
      { type: 'pinned' },
      { type: 'archive' },
      { type: 'tag', value: 'x' },
      { type: 'group', value: 'frame_z' },
    ]) {
      localStorage.setItem('deen.migrate.outer-canvas.v1', 'done');
      mockFetchSequence([{ state, updated_at: '...' }]);
      const { container, unmount } = render(
        <OuterCanvas
          notes={notes} groups={[]}
          overlay={fakeOverlay({ pinnedIds: ['n1'] })}
          filter={filter} onOpenNote={() => {}}
        />,
      );
      await waitFor(() =>
        expect(container.querySelector('.oc-root')).not.toBeNull(),
      );
      unmount();
    }
  });
});
