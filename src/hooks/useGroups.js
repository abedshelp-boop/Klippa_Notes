import { useCallback, useEffect, useState } from 'react';
import { debug } from '../lib/debug';

const API_URL = 'http://localhost:8765';
const MAX_RETRIES = 10;
const RETRY_DELAY_MS = 1500;

/**
 * useGroups (Phase 9).
 *
 * Manages the in-memory group list. Notes' `group_id` lives on the Note
 * objects themselves (managed by useNotes); this hook only owns the group
 * metadata (id, name, parent_id, timestamps).
 *
 * Mutations write through to the Python service AND optimistically update
 * the local state. The WS broadcasts (`group_created`, `group_updated`,
 * `group_deleted`) handle cross-window sync.
 */
export default function useGroups() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchGroups = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/groups`);
      if (res.ok) {
        const data = await res.json();
        setGroups(Array.isArray(data) ? data : []);
        setLoading(false);
        return true;
      }
    } catch {
      // Python service likely still starting — caller retries.
    }
    return false;
  }, []);

  // Initial load with retry, same shape as useNotes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let i = 0; i < MAX_RETRIES; i++) {
        if (cancelled) return;
        const ok = await fetchGroups();
        if (ok) return;
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      }
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [fetchGroups]);

  const createGroup = useCallback(async (name, parentId = null) => {
    try {
      const res = await fetch(`${API_URL}/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, parent_id: parentId }),
      });
      if (!res.ok) {
        debug.error('Groups', 'create failed', res.status);
        return null;
      }
      const group = await res.json();
      setGroups((prev) => {
        if (prev.some((g) => g.id === group.id)) return prev;
        return [...prev, group].sort((a, b) =>
          a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
        );
      });
      return group;
    } catch (err) {
      debug.error('Groups', 'create failed', err);
      return null;
    }
  }, []);

  const renameGroup = useCallback(async (id, name) => {
    try {
      const res = await fetch(`${API_URL}/groups/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        debug.error('Groups', 'rename failed', res.status);
        return null;
      }
      const group = await res.json();
      setGroups((prev) =>
        prev.map((g) => (g.id === group.id ? group : g))
          .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })),
      );
      return group;
    } catch (err) {
      debug.error('Groups', 'rename failed', err);
      return null;
    }
  }, []);

  const reparentGroup = useCallback(async (id, parentId) => {
    try {
      const res = await fetch(`${API_URL}/groups/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent_id: parentId }),
      });
      if (!res.ok) {
        debug.error('Groups', 'reparent failed', res.status);
        return null;
      }
      const group = await res.json();
      setGroups((prev) =>
        prev.map((g) => (g.id === group.id ? group : g)),
      );
      return group;
    } catch (err) {
      debug.error('Groups', 'reparent failed', err);
      return null;
    }
  }, []);

  const deleteGroup = useCallback(async (id) => {
    try {
      const res = await fetch(`${API_URL}/groups/${id}`, { method: 'DELETE' });
      if (!res.ok) return false;
      setGroups((prev) => {
        // Orphan subgroups to root locally so the UI matches the DB
        // (the server already did the same via manual cascade).
        return prev
          .filter((g) => g.id !== id)
          .map((g) => (g.parent_id === id ? { ...g, parent_id: null } : g));
      });
      return true;
    } catch (err) {
      debug.error('Groups', 'delete failed', err);
      return false;
    }
  }, []);

  return {
    groups,
    loading,
    refetch: fetchGroups,
    createGroup,
    renameGroup,
    reparentGroup,
    deleteGroup,
  };
}
