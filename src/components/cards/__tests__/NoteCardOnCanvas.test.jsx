import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import NoteCardOnCanvas from '../NoteCardOnCanvas.jsx';

function wrap(ui) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

describe('NoteCardOnCanvas', () => {
  const note = {
    id: 'n1',
    title: 'Sapiens — Chapter 3',
    content: 'A brief history note about agricultural revolution and grain.',
    created_at: '2026-05-24T00:00:00Z',
    updated_at: '2026-05-24T00:00:00Z',
  };

  it('renders the note title', () => {
    wrap(<NoteCardOnCanvas data={{
      note, pinned: false, tags: [], archived: false,
    }} />);
    expect(screen.getByText(/Sapiens — Chapter 3/)).toBeInTheDocument();
  });

  it('shows a preview snippet', () => {
    wrap(<NoteCardOnCanvas data={{
      note, pinned: false, tags: [], archived: false,
    }} />);
    expect(screen.getByText(/agricultural revolution/i)).toBeInTheDocument();
  });

  it('shows pin indicator when pinned', () => {
    wrap(<NoteCardOnCanvas data={{
      note, pinned: true, tags: [], archived: false,
    }} />);
    expect(screen.getByLabelText(/pinned/i)).toBeInTheDocument();
  });

  it('shows up to 2 tag chips', () => {
    wrap(<NoteCardOnCanvas data={{
      note, pinned: false, tags: ['focus', 'urgent', 'extra'], archived: false,
    }} />);
    expect(screen.getByText('focus')).toBeInTheDocument();
    expect(screen.getByText('urgent')).toBeInTheDocument();
    expect(screen.queryByText('extra')).not.toBeInTheDocument();
  });

  it('applies an archived modifier class when archived', () => {
    const { container } = wrap(
      <NoteCardOnCanvas data={{
        note, pinned: false, tags: [], archived: true,
      }} />,
    );
    expect(container.querySelector('.oc-card.is-archived')).not.toBeNull();
  });

  it('falls back to "Untitled Note" when title is empty', () => {
    wrap(<NoteCardOnCanvas data={{
      note: { ...note, title: '' },
      pinned: false, tags: [], archived: false,
    }} />);
    expect(screen.getByText(/Untitled Note/i)).toBeInTheDocument();
  });

  it('renders "No preview available" when content is empty', () => {
    wrap(<NoteCardOnCanvas data={{
      note: { ...note, content: '' },
      pinned: false, tags: [], archived: false,
    }} />);
    expect(screen.getByText(/No preview available/i)).toBeInTheDocument();
  });

  it('calls onOpen when the card body is clicked', () => {
    const onOpen = vi.fn();
    wrap(<NoteCardOnCanvas data={{
      note, pinned: false, tags: [], archived: false, onOpen,
    }} />);
    fireEvent.click(screen.getByText(/Sapiens — Chapter 3/));
    expect(onOpen).toHaveBeenCalledWith('n1');
  });

  it('renders source AND target handles for free-form connections', () => {
    const { container } = wrap(
      <NoteCardOnCanvas data={{
        note, pinned: false, tags: [], archived: false,
      }} />,
    );
    // React Flow handles render as elements with class react-flow__handle.
    const handles = container.querySelectorAll('.react-flow__handle');
    expect(handles.length).toBeGreaterThanOrEqual(2);
  });

  it('does not call onOpen when a handle is clicked', () => {
    const onOpen = vi.fn();
    const { container } = wrap(
      <NoteCardOnCanvas data={{
        note, pinned: false, tags: [], archived: false, onOpen,
      }} />,
    );
    const handle = container.querySelector('.react-flow__handle');
    fireEvent.click(handle);
    expect(onOpen).not.toHaveBeenCalled();
  });
});
