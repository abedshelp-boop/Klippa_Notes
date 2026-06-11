import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import WindowChrome from './components/WindowChrome';
import Home from './components/Home';
import InnerCanvas from './components/InnerCanvas';
import Listening from './components/Listening';
import Settings from './components/Settings';
import MoveToGroupModal from './components/MoveToGroupModal';
import useNotes from './hooks/useNotes';
import useWebSocket from './hooks/useWebSocket';
import useNoteOverlay from './hooks/useNoteOverlay';
import useGroups from './hooks/useGroups';
import { debug } from './lib/debug';

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
  const [moveModalNoteId, setMoveModalNoteId] = useState(null);

  const captureTimeoutRef = useRef(null);
  const savedFlashTimeoutRef = useRef(null);
  const searchDebounceRef = useRef(null);

  const {
    notes,
    addNote,
    updateNote,
    deleteNote,
    searchNotes,
    createNoteOnServer,
    updateNoteOnServer,
  } = useNotes();
  const overlay = useNoteOverlay();
  const {
    groups,
    createGroup,
    renameGroup,
    deleteGroup,
  } = useGroups();

  // One-time migration: drain any titleOverride entries from the overlay's
  // localStorage state into real DB titles via PUT /notes/{id}. Runs once
  // ever per install — gated by deen.migrate.titles.v1.
  useEffect(() => {
    const FLAG = 'deen.migrate.titles.v1';
    if (typeof localStorage === 'undefined') return;
    if (localStorage.getItem(FLAG) === 'done') return;
    if (notes.length === 0) return; // wait until first notes load

    let cancelled = false;
    (async () => {
      try {
        const raw = localStorage.getItem('deen.overlay.v1');
        if (!raw) {
          localStorage.setItem(FLAG, 'done');
          return;
        }
        const parsed = JSON.parse(raw);
        const overrides = parsed.titleOverride || {};
        const entries = Object.entries(overrides);
        if (entries.length === 0) {
          localStorage.setItem(FLAG, 'done');
          return;
        }
        for (const [id, title] of entries) {
          if (cancelled) return;
          if (!title || typeof title !== 'string') continue;
          await updateNoteOnServer(id, { title });
        }
        // Clear the titleOverride field; preserve pinned/trashed/userTags.
        parsed.titleOverride = {};
        localStorage.setItem('deen.overlay.v1', JSON.stringify(parsed));
        localStorage.setItem(FLAG, 'done');
      } catch (err) {
        debug.warn('migration', 'titleOverride drain failed', err);
        // Don't set the flag — let it retry next launch.
      }
    })();
    return () => { cancelled = true; };
  }, [notes.length, updateNoteOnServer]);

  // One-time migration: backfill canvas_state for every note that doesn't
  // have one yet (canvas redesign sub-project 1). Lossless — each pre-
  // redesign note becomes a single TextCard at (0,0) holding its existing
  // content. Idempotent: if all notes already have canvas_state, this is
  // a no-op + flag set. Same pattern as the titleOverride drain above.
  useEffect(() => {
    const FLAG = 'deen.migrate.canvas.v1';
    if (typeof localStorage === 'undefined') return;
    if (localStorage.getItem(FLAG) === 'done') return;
    if (notes.length === 0) return; // wait for first notes load

    let cancelled = false;
    (async () => {
      try {
        // Lazy-import so the migration module isn't in the critical path
        // when the flag is already set.
        const { migrateLegacyMarkdown } = await import('./lib/canvas/migrate.js');
        // useState([]) typed `notes` as never[] in jsconfig strict mode;
        // re-bind with `any[]` so the loop can read note.canvas_state etc.
        // without verbose per-line casts. Pre-existing typing gap, not new.
        /** @type {any[]} */
        const all = notes;
        for (const note of all) {
          if (cancelled) return;
          if (note.canvas_state != null) continue; // already migrated
          const next = migrateLegacyMarkdown(note.content || '');
          await updateNoteOnServer(note.id, { canvas_state: next });
        }
        if (!cancelled) localStorage.setItem(FLAG, 'done');
      } catch (err) {
        debug.warn('migration', 'canvas_state backfill failed', err);
        // Don't set the flag — let it retry on next launch.
      }
    })();
    return () => { cancelled = true; };
  }, [notes.length, updateNoteOnServer]); // notes.length so we don't rerun on every WS update

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
      debug.error('App', 'trigger failed', err);
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

  const handleCreateEmptyNote = useCallback(async () => {
    const note = await createNoteOnServer({
      title: 'Untitled Note',
      content: '',
    });
    if (note) {
      setActiveNoteId(note.id);
      setView('note');
      setPendingEditId(note.id);
    }
  }, [createNoteOnServer]);

  // Electron-driven "open this note in edit mode" — used by the picker's
  // "+ Create empty note" row, which creates the note in the main process
  // and asks the renderer to land on it.
  useEffect(() => {
    const api = window.electronAPI;
    if (!api?.onOpenNote) return;
    const unsubscribe = api.onOpenNote((id) => {
      if (!id) return;
      setActiveNoteId(id);
      setView('note');
      setPendingEditId(id);
    });
    return unsubscribe;
  }, []);

  // Sub-project 5: push the open-note id to electron whenever the active view
  // changes, so Python's context_state knows whether a no-qualifier "Hey Deen,
  // [content]" capture should land in the open note (vs. Quick Inbox).
  useEffect(() => {
    const api = window.electronAPI;
    if (!api?.notifyOpenNote) return;
    const id = view === 'note' ? activeNoteId : null;
    api.notifyOpenNote(id).catch(() => {});
  }, [view, activeNoteId]);

  const deletePermanently = useCallback(async (id) => {
    // Sub-project 5: Quick Inbox is undeletable. Don't even attempt the DELETE
    // — Python returns 409, which we'd only have to render an error for.
    const target = notes.find((n) => n.id === id);
    if (target?.is_quick_inbox) {
      debug.log('App', 'refusing delete of Quick Inbox');
      return;
    }
    const success = await deleteNote(id);
    if (success) {
      overlay.forgetNote(id);
      if (activeNoteId === id) {
        setView('home');
        setActiveNoteId(null);
      }
    }
  }, [deleteNote, overlay, activeNoteId, notes]);

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
    if (filter.type === 'group') {
      // Direct children of the selected group only — to see nested groups'
      // notes, the user expands and clicks the subgroup.
      return notes.filter(
        (n) => n.group_id === filter.value && !trashed(n.id),
      );
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

  const handleMoveToGroup = useCallback(async (groupId) => {
    if (!moveModalNoteId) return;
    await updateNoteOnServer(moveModalNoteId, { group_id: groupId });
  }, [moveModalNoteId, updateNoteOnServer]);

  const activeMoveNote = notes.find((n) => n.id === moveModalNoteId) || null;

  return (
    <div className="app-shell">
      {/* Phase 5: WindowChrome floats at the literal top-right of the
          viewport (position: fixed). Lives outside <main> so it isn't
          affected by any inner overflow/padding. */}
      <WindowChrome />

      <main className="app-main">
        <Toolbar
          query={query}
          onQueryChange={handleQueryChange}
          onCreateNote={handleCreateEmptyNote}
        />
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
                onCreateNote={handleCreateEmptyNote}
                onMoveToGroup={(id) => setMoveModalNoteId(id)}
                onRenameNote={(id, title) => updateNoteOnServer(id, { title })}
              />
            )}
            {view === 'note' && activeNote && (
              <InnerCanvas
                note={activeNote}
                onBack={handleBack}
                onDeletePermanently={deletePermanently}
                overlay={overlay}
                startInEdit={pendingEditId === activeNote.id}
                onEditConsumed={() => setPendingEditId(null)}
                onUpdateNote={updateNoteOnServer}
                onMoveToGroup={() => setMoveModalNoteId(activeNote.id)}
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
                onCreateNote={handleCreateEmptyNote}
                onMoveToGroup={(id) => setMoveModalNoteId(id)}
                onRenameNote={(id, title) => updateNoteOnServer(id, { title })}
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
        onOpenNote={handleOpenNote}
        onOpenSettings={() => setShowSettings(true)}
        status={status}
        capturing={capturing}
        overlay={overlay}
        onCreateNote={handleCreateEmptyNote}
        groups={groups}
        onCreateGroup={createGroup}
        onRenameGroup={renameGroup}
        onDeleteGroup={deleteGroup}
      />

      {capturing && (
        <Listening
          stage={listeningStage}
          transcript={''}
          onDismiss={dismissCapture}
        />
      )}

      {showSettings && <Settings onClose={() => setShowSettings(false)} />}

      {moveModalNoteId && activeMoveNote && (
        <MoveToGroupModal
          noteTitle={activeMoveNote.title}
          currentGroupId={activeMoveNote.group_id || null}
          groups={groups}
          onMove={handleMoveToGroup}
          onCreateGroup={createGroup}
          onClose={() => setMoveModalNoteId(null)}
        />
      )}
    </div>
  );
}
