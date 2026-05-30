import React from 'react';
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import InnerCanvas from '../InnerCanvas.jsx';

// `previewMode` short-circuits the React Flow tree (which needs
// ResizeObserver + DOM) so renderToStaticMarkup can assert on the
// rail + a static card list in vitest's node env.

const baseOverlay = {
  isPinned: () => false,
  isTrashed: () => false,
  togglePinned: () => {},
  trashNote: () => {},
  restoreNote: () => {},
  getUserTags: () => [],
  addUserTag: () => {},
  removeUserTag: () => {},
};

const noteFixture = {
  id: 'n_test',
  title: 'A test note',
  content: '# heading\n\nbody',
  created_at: '2026-05-25T00:00:00Z',
  canvas_state: null,
};

describe('InnerCanvas', () => {
  it('renders the note title in the rail', () => {
    const html = renderToStaticMarkup(
      <InnerCanvas
        note={noteFixture}
        overlay={baseOverlay}
        onBack={() => {}}
        onDeletePermanently={() => {}}
        onUpdateNote={() => {}}
        onMoveToGroup={() => {}}
        previewMode
      />,
    );
    expect(html).toContain('A test note');
  });

  it('renders the legacy content as a TextCard when canvas_state is null', () => {
    const html = renderToStaticMarkup(
      <InnerCanvas
        note={noteFixture}
        overlay={baseOverlay}
        onBack={() => {}}
        onDeletePermanently={() => {}}
        onUpdateNote={() => {}}
        onMoveToGroup={() => {}}
        previewMode
      />,
    );
    expect(html).toContain('ic-textcard');
    expect(html).toContain('heading');
    expect(html).toContain('body');
  });

  it('uses canvas_state when present', () => {
    const note = {
      ...noteFixture,
      content: 'legacy ignored',
      canvas_state: {
        schemaVersion: 1,
        cards: [{
          id: 'card_x', type: 'text',
          position: { x: 0, y: 0 }, size: { w: 320, h: 200 },
          rotation: 0, frameId: null,
          data: { markdown: 'from canvas_state' },
        }],
        frames: [], connectors: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    };
    const html = renderToStaticMarkup(
      <InnerCanvas
        note={note}
        overlay={baseOverlay}
        onBack={() => {}}
        onDeletePermanently={() => {}}
        onUpdateNote={() => {}}
        onMoveToGroup={() => {}}
        previewMode
      />,
    );
    expect(html).toContain('from canvas_state');
    expect(html).not.toContain('legacy ignored');
  });

  it('renders nothing when note is null', () => {
    const html = renderToStaticMarkup(
      <InnerCanvas
        note={null}
        overlay={baseOverlay}
        onBack={() => {}}
        onDeletePermanently={() => {}}
        onUpdateNote={() => {}}
        onMoveToGroup={() => {}}
        previewMode
      />,
    );
    expect(html).toBe('');
  });
});
