import { useState, useEffect, useCallback } from 'react';

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
      console.log('[Notes] Backend not available yet');
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
    setNotes((prev) => [note, ...prev]);
  }, []);

  const updateNote = useCallback((updated) => {
    setNotes((prev) =>
      prev.map((n) => (n.id === updated.id ? updated : n))
    );
  }, []);

  const deleteNote = useCallback(async (id) => {
    try {
      const res = await fetch(`${API_URL}/notes/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setNotes((prev) => prev.filter((n) => n.id !== id));
        return true;
      }
    } catch (err) {
      console.error('[Notes] Delete failed:', err);
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
      console.error('[Notes] Search failed:', err);
    }
  }, [fetchNotes]);

  return { notes, loading, addNote, updateNote, deleteNote, searchNotes, refetch: fetchNotes };
}
