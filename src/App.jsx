import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import Home from './components/Home';
import NoteView from './components/NoteView';
import Listening from './components/Listening';
import Settings from './components/Settings';
import useNotes from './hooks/useNotes';
import useWebSocket from './hooks/useWebSocket';
import useNoteOverlay from './hooks/useNoteOverlay';

const API_URL = 'http://localhost:8765';
const CAPTURE_TIMEOUT_MS = 30000;

export default function App() {
  const [view, setView] = useState('home');
  const [activeNoteId, setActiveNoteId] = useState(null);
  const [filter, setFilter] = useState({ type: 'all' });
  const [query, setQuery] = useState('');
  const [capturing, setCapturing] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [pendingEditId, setPendingEditId] = useState(null);

  const captureTimeoutRef = useRef(null);
  const savedFlashTimeoutRef = useRef(null);
  const searchDebounceRef = useRef(null);

  const { notes, addNote, updateNote, deleteNote, searchNotes } = useNotes();
  const overlay = useNoteOverlay();

  const clearCapture = useCallback(() => {
    setCapturing(false);
    if (captureTimeoutRef.current) {
      clearTimeout(captureTimeoutRef.current);
      captureTimeoutRef.current = null;
    }
  }, []);

  const flashSaved = useCallback(() => {
    setSavedFlash(true);
    if (savedFlashTimeoutRef.current) clearTimeout(savedFlashTimeoutRef.current);
    savedFlashTimeoutRef.current = setTimeout(() => {
      setSavedFlash(false);
      clearCapture();
    }, 1400);
  }, [clearCapture]);

  const handleNewNote = useCallback((note) => {
    addNote(note);
    setActiveNoteId(note.id);
    setView('note');
    if (capturing) flashSaved();
  }, [addNote, capturing, flashSaved]);

  const handleNoteUpdated = useCallback((note) => {
    updateNote(note);
    if (capturing) flashSaved();
  }, [updateNote, capturing, flashSaved]);

  const { status } = useWebSocket(handleNewNote, handleNoteUpdated);

  const triggerCapture = useCallback(async () => {
    if (capturing) return;
    setCapturing(true);
    if (captureTimeoutRef.current) clearTimeout(captureTimeoutRef.current);
    captureTimeoutRef.current = setTimeout(() => {
      setCapturing(false);
      captureTimeoutRef.current = null;
    }, CAPTURE_TIMEOUT_MS);
    try {
      if (window.electronAPI?.triggerNote) {
        await window.electronAPI.triggerNote();
      } else {
        await fetch(`${API_URL}/trigger`, { method: 'POST' });
      }
    } catch (err) {
      console.error('[App] Trigger failed:', err);
      clearCapture();
    }
  }, [capturing, clearCapture]);

  const dismissCapture = useCallback(() => {
    clearCapture();
    setSavedFlash(false);
    if (savedFlashTimeoutRef.current) clearTimeout(savedFlashTimeoutRef.current);
  }, [clearCapture]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (capturing) { dismissCapture(); return; }
        if (showSettings) { setShowSettings(false); return; }
        if (view === 'note') { setView('home'); setActiveNoteId(null); }
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        triggerCapture();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const input = document.querySelector('.toolbar-search-input');
        if (input) input.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [view, capturing, showSettings, dismissCapture, triggerCapture]);

  useEffect(() => {
    return () => {
      if (captureTimeoutRef.current) clearTimeout(captureTimeoutRef.current);
      if (savedFlashTimeoutRef.current) clearTimeout(savedFlashTimeoutRef.current);
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    };
  }, []);

  const handleQueryChange = useCallback((value) => {
    setQuery(value);
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => {
      searchNotes(value);
    }, 180);
  }, [searchNotes]);

  const handleOpenNote = useCallback((id) => {
    setActiveNoteId(id);
    setView('note');
  }, []);

  const handleBack = useCallback(() => {
    setView('home');
    setActiveNoteId(null);
  }, []);

  const deletePermanently = useCallback(async (id) => {
    const success = await deleteNote(id);
    if (success) {
      overlay.forgetNote(id);
      if (activeNoteId === id) {
        setView('home');
        setActiveNoteId(null);
      }
    }
  }, [deleteNote, overlay, activeNoteId]);

  const handleFilterChange = useCallback((f) => {
    setFilter(f);
    if (view === 'note') { setView('home'); setActiveNoteId(null); }
  }, [view]);

  const visibleNotes = useMemo(() => {
    const trashed = (id) => overlay.isTrashed(id);
    const pinned = (id) => overlay.isPinned(id);
    const hasTag = (id, tag) => overlay.getUserTags(id).includes(tag);

    if (filter.type === 'archive') return notes.filter((n) => trashed(n.id));
    if (filter.type === 'pinned') {
      return notes.filter((n) => pinned(n.id) && !trashed(n.id));
    }
    if (filter.type === 'tag') {
      return notes.filter((n) => hasTag(n.id, filter.value) && !trashed(n.id));
    }
    return notes.filter((n) => !trashed(n.id));
  }, [notes, filter, overlay]);

  const activeNote = notes.find((n) => n.id === activeNoteId) || null;

  const listeningStage = savedFlash
    ? 'saved'
    : status === 'command'
      ? 'command'
      : status === 'processing'
        ? 'processing'
        : 'listening';

  const triggerEdit = (id) => {
    setActiveNoteId(id);
    setView('note');
    setPendingEditId(id);
  };

  return (
    <div className="app-shell">
      <main className="app-main">
        <Toolbar query={query} onQueryChange={handleQueryChange} />
        <div className="app-content">
          <div className="app-scroll">
            {view === 'home' && (
              <Home
                notes={visibleNotes}
                filter={filter}
                onFilterChange={handleFilterChange}
                onOpenNote={handleOpenNote}
                overlay={overlay}
                onEditNote={triggerEdit}
                onDeletePermanently={deletePermanently}
              />
            )}
            {view === 'note' && activeNote && (
              <NoteView
                note={activeNote}
                onBack={handleBack}
                onDeletePermanently={deletePermanently}
                overlay={overlay}
                startInEdit={pendingEditId === activeNote.id}
                onEditConsumed={() => setPendingEditId(null)}
              />
            )}
            {view === 'note' && !activeNote && (
              <Home
                notes={visibleNotes}
                filter={filter}
                onFilterChange={handleFilterChange}
                onOpenNote={handleOpenNote}
                overlay={overlay}
                onEditNote={triggerEdit}
                onDeletePermanently={deletePermanently}
              />
            )}
          </div>
        </div>
      </main>

      <Sidebar
        notes={notes}
        filter={filter}
        onFilterChange={handleFilterChange}
        onListen={triggerCapture}
        onOpenSettings={() => setShowSettings(true)}
        status={status}
        capturing={capturing}
        overlay={overlay}
      />

      {capturing && (
        <Listening
          stage={listeningStage}
          transcript={''}
          onDismiss={dismissCapture}
        />
      )}

      {showSettings && <Settings onClose={() => setShowSettings(false)} />}
    </div>
  );
}
