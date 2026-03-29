import React, { useState, useCallback } from 'react';
import NoteCard from './NoteCard';

const API_URL = 'http://localhost:8765';

export default function NoteList({ notes, activeNoteId, onSelectNote, onSearch, onOpenSettings }) {
  const [query, setQuery] = useState('');
  const [capturing, setCapturing] = useState(false);

  const handleSearchChange = useCallback((e) => {
    const val = e.target.value;
    setQuery(val);
    onSearch(val);
  }, [onSearch]);

  const handleCaptureNote = useCallback(async () => {
    setCapturing(true);
    try {
      if (window.electronAPI?.triggerNote) {
        await window.electronAPI.triggerNote();
      } else {
        await fetch(`${API_URL}/trigger`, { method: 'POST' });
      }
    } catch (err) {
      console.error('Trigger failed:', err);
    }
    setTimeout(() => setCapturing(false), 3000);
  }, []);

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">Notes</div>
        <input
          className="search-box"
          type="text"
          placeholder="Search notes..."
          value={query}
          onChange={handleSearchChange}
        />
      </div>

      <div className="note-list">
        {notes.length === 0 ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            {query ? 'No notes match your search' : 'No notes yet. Press Ctrl+Shift+N or click the button below.'}
          </div>
        ) : (
          notes.map((note) => (
            <NoteCard
              key={note.id}
              note={note}
              isActive={note.id === activeNoteId}
              onClick={() => onSelectNote(note.id)}
            />
          ))
        )}
      </div>

      <div className="sidebar-actions">
        <button
          className="sidebar-btn capture-btn"
          onClick={handleCaptureNote}
          disabled={capturing}
        >
          {capturing ? 'Capturing...' : 'Capture Note'}
        </button>
        <button className="sidebar-btn" onClick={onOpenSettings}>Settings</button>
      </div>
    </div>
  );
}
