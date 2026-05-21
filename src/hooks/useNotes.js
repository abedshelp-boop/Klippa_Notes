import { useState, useEffect, useCallback } from 'react';
import { debug } from '../lib/debug';

const API_URL = 'http://localhost:8765';
const MAX_RETRIES = 10;
const RETRY_DELAY_MS = 1500;

export default function useNotes() {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchNotes = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/notes`);
      if (res.ok) {
        const data = await res.json();
        setNotes(data);
        setLoading(false);
        return true;
      }
    } catch {
      debug.log('Notes', 'backend not available yet');
    }
    return false;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadWithRetry() {
      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        if (cancelled) return;
        const ok = await fetchNotes();
        if (ok) return;
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      }
      if (!cancelled) setLoading(false);
    }

    loadWithRetry();
    return () => { cancelled = true; };
  }, [fetchNotes]);

  const addNote = useCallback((note) => {
    setNotes((prev) => {
      // De-dup in case the WS broadcast lands before this hook's caller adds.
      if (prev.some((n) => n.id === note.id)) return prev;
      return [note, ...prev];
    });
  }, []);

  const updateNote = useCallback((updated) => {
    setNotes((prev) =>
      prev.map((n) => (n.id === updated.id ? updated : n))
    );
  }, []);

  /**
   * Create a new note on the server (independent of the audio pipeline).
   * Returns the new note dict on success or null on failure.
   * The WebSocket will also broadcast the same note shortly after — the
   * de-dup in addNote prevents double-insert.
   */
  const createNoteOnServer = useCallback(async (initial = {}) => {
    try {
      const res = await fetch(`${API_URL}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(initial),
      });
      if (!res.ok) {
        debug.error('Notes', 'create failed', res.status);
        return null;
      }
      const note = await res.json();
      setNotes((prev) => {
        if (prev.some((n) => n.id === note.id)) return prev;
        return [note, ...prev];
      });
      return note;
    } catch (err) {
      debug.error('Notes', 'create failed', err);
      return null;
    }
  }, []);

  /**
   * Patch a note on the server. Patch keys: title, content, tags, source,
   * group_id (null detaches from a group). Returns the updated note dict on
   * success or null on failure.
   */
  const updateNoteOnServer = useCallback(async (id, patch) => {
    try {
      const res = await fetch(`${API_URL}/notes/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        debug.error('Notes', 'update failed', res.status);
        return null;
      }
      const note = await res.json();
      setNotes((prev) =>
        prev.map((n) => (n.id === note.id ? note : n))
      );
      return note;
    } catch (err) {
      debug.error('Notes', 'update failed', err);
      return null;
    }
  }, []);

  const deleteNote = useCallback(async (id) => {
    try {
      const res = await fetch(`${API_URL}/notes/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setNotes((prev) => prev.filter((n) => n.id !== id));
        return true;
      }
    } catch (err) {
      debug.error('Notes', 'delete failed', err);
    }
    return false;
  }, []);

  const searchNotes = useCallback(async (query) => {
    if (!query.trim()) {
      return fetchNotes();
    }
    try {
      const res = await fetch(`${API_URL}/notes/search?q=${encodeURIComponent(query)}`);
      if (res.ok) {
        const data = await res.json();
        setNotes(data);
      }
    } catch (err) {
      debug.error('Notes', 'search failed', err);
    }
  }, [fetchNotes]);

  return {
    notes,
    loading,
    addNote,
    updateNote,
    deleteNote,
    searchNotes,
    refetch: fetchNotes,
    createNoteOnServer,
    updateNoteOnServer,
  };
}
