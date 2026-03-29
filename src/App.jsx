import React, { useState, useCallback } from 'react';
import NoteList from './components/NoteList';
import NoteViewer from './components/NoteViewer';
import StatusBar from './components/StatusBar';
import Settings from './components/Settings';
import useNotes from './hooks/useNotes';
import useWebSocket from './hooks/useWebSocket';

export default function App() {
  const [activeNoteId, setActiveNoteId] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  const { notes, addNote, updateNote, deleteNote, searchNotes } = useNotes();

  const handleNewNote = useCallback((note) => {
    addNote(note);
    setActiveNoteId(note.id);
  }, [addNote]);

  const handleNoteUpdated = useCallback((note) => {
    updateNote(note);
    setActiveNoteId(note.id);
  }, [updateNote]);

  const { status } = useWebSocket(handleNewNote, handleNoteUpdated);

  const activeNote = notes.find((n) => n.id === activeNoteId) || null;

  const handleDelete = useCallback(async (id) => {
    const success = await deleteNote(id);
    if (success && activeNoteId === id) {
      setActiveNoteId(null);
    }
  }, [deleteNote, activeNoteId]);

  return (
    <div className="app-container">
      <div className="title-bar">
        <span className="title-bar-label">KLIPPA</span>
        <div className="title-bar-controls">
          <button
            className="title-bar-btn minimize"
            onClick={() => window.electronAPI?.minimize()}
          />
          <button
            className="title-bar-btn maximize"
            onClick={() => window.electronAPI?.maximize()}
          />
          <button
            className="title-bar-btn close"
            onClick={() => window.electronAPI?.close()}
          />
        </div>
      </div>

      <div className="main-content">
        <NoteList
          notes={notes}
          activeNoteId={activeNoteId}
          onSelectNote={setActiveNoteId}
          onSearch={searchNotes}
          onOpenSettings={() => setShowSettings(true)}
        />
        <NoteViewer note={activeNote} onDelete={handleDelete} />
      </div>

      <StatusBar status={status} noteCount={notes.length} />

      {showSettings && <Settings onClose={() => setShowSettings(false)} />}
    </div>
  );
}
