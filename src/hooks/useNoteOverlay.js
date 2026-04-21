import { useCallback, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'deen.overlay.v1';

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw);
    return {
      pinned: parsed.pinned || {},
      trashed: parsed.trashed || {},
      userTags: parsed.userTags || {},
      titleOverride: parsed.titleOverride || {},
    };
  } catch {
    return emptyState();
  }
}

function emptyState() {
  return { pinned: {}, trashed: {}, userTags: {}, titleOverride: {} };
}

function pruneFalsy(map) {
  const out = {};
  for (const [k, v] of Object.entries(map)) if (v) out[k] = true;
  return out;
}

export default function useNoteOverlay() {
  const [state, setState] = useState(loadState);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
      console.warn('[overlay] persist failed', err);
    }
  }, [state]);

  const togglePinned = useCallback((id) => {
    setState((prev) => ({
      ...prev,
      pinned: pruneFalsy({ ...prev.pinned, [id]: !prev.pinned[id] }),
    }));
  }, []);

  const trashNote = useCallback((id) => {
    setState((prev) => ({
      ...prev,
      trashed: { ...prev.trashed, [id]: true },
      pinned: pruneFalsy({ ...prev.pinned, [id]: false }),
    }));
  }, []);

  const restoreNote = useCallback((id) => {
    setState((prev) => ({
      ...prev,
      trashed: pruneFalsy({ ...prev.trashed, [id]: false }),
    }));
  }, []);

  const forgetNote = useCallback((id) => {
    setState((prev) => {
      const pinned = { ...prev.pinned }; delete pinned[id];
      const trashed = { ...prev.trashed }; delete trashed[id];
      const userTags = { ...prev.userTags }; delete userTags[id];
      const titleOverride = { ...prev.titleOverride }; delete titleOverride[id];
      return { pinned, trashed, userTags, titleOverride };
    });
  }, []);

  const addUserTag = useCallback((id, tag) => {
    const normalized = tag.trim();
    if (!normalized) return;
    setState((prev) => {
      const existing = prev.userTags[id] || [];
      if (existing.some((t) => t.toLowerCase() === normalized.toLowerCase())) return prev;
      return {
        ...prev,
        userTags: { ...prev.userTags, [id]: [...existing, normalized] },
      };
    });
  }, []);

  const removeUserTag = useCallback((id, tag) => {
    setState((prev) => {
      const existing = prev.userTags[id] || [];
      const next = existing.filter((t) => t !== tag);
      const userTags = { ...prev.userTags };
      if (next.length === 0) delete userTags[id];
      else userTags[id] = next;
      return { ...prev, userTags };
    });
  }, []);

  const setTitleOverride = useCallback((id, title) => {
    setState((prev) => {
      const titleOverride = { ...prev.titleOverride };
      const trimmed = (title || '').trim();
      if (!trimmed) delete titleOverride[id];
      else titleOverride[id] = trimmed;
      return { ...prev, titleOverride };
    });
  }, []);

  const isPinned = useCallback((id) => !!state.pinned[id], [state.pinned]);
  const isTrashed = useCallback((id) => !!state.trashed[id], [state.trashed]);
  const getUserTags = useCallback((id) => state.userTags[id] || [], [state.userTags]);
  const getTitleOverride = useCallback((id) => state.titleOverride[id], [state.titleOverride]);

  const pinnedIds = useMemo(
    () => Object.keys(state.pinned).filter((id) => state.pinned[id]),
    [state.pinned],
  );
  const trashedIds = useMemo(
    () => Object.keys(state.trashed).filter((id) => state.trashed[id]),
    [state.trashed],
  );
  const allUserTags = useMemo(() => {
    const counts = new Map();
    for (const tags of Object.values(state.userTags)) {
      for (const t of tags) counts.set(t, (counts.get(t) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [state.userTags]);

  return {
    isPinned,
    isTrashed,
    getUserTags,
    getTitleOverride,
    togglePinned,
    trashNote,
    restoreNote,
    forgetNote,
    addUserTag,
    removeUserTag,
    setTitleOverride,
    pinnedIds,
    trashedIds,
    allUserTags,
  };
}
