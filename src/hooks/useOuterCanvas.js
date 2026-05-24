import { useCallback, useEffect, useRef, useState } from 'react';
import { debug } from '../lib/debug';
import {
  migrateLegacyToOuterCanvas,
  createNoteCard,
} from '../lib/canvas/outer.js';
import {
  isOuterCanvasState,
  emptyOuterCanvasState,
} from '../lib/canvas/validators.js';

const API_URL = 'http://localhost:8765';
const MIGRATION_FLAG = 'deen.migrate.outer-canvas.v1';

/**
 * Owns the outer-canvas state lifecycle:
 *
 *  - Loads from GET /outer-canvas on mount.
 *  - If no state on the server AND the migration flag is unset, runs
 *    `migrateLegacyToOuterCanvas` against the live notes/groups/overlay and
 *    PUTs the result. Sets the flag so it never re-migrates.
 *  - Reconciles when `notes` changes: notes not yet on the canvas land on the
 *    canvas floor; cards whose note has been deleted are dropped.
 *  - `commit(nextState)` persists via PUT.
 *
 * @param {{
 *   notes: Array<{ id: string, group_id?: string | null,
 *                  created_at?: string, updated_at?: string }>,
 *   groups: Array<{ id: string, name: string, parent_id?: string | null }>,
 *   overlay: {
 *     isPinned: (id: string) => boolean,
 *     isTrashed: (id: string) => boolean,
 *     getUserTags: (id: string) => string[],
 *   },
 * }} args
 */
export default function useOuterCanvas({ notes, groups, overlay }) {
  /** @type {[import('../lib/types.js').OuterCanvasState | null,
   *         React.Dispatch<React.SetStateAction<any>>]} */
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const didMigrate = useRef(false);

  const persist = useCallback(async (nextState) => {
    try {
      const res = await fetch(`${API_URL}/outer-canvas`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: nextState }),
      });
      if (!res.ok) debug.error('OuterCanvas', 'PUT failed', res.status);
    } catch (err) {
      debug.error('OuterCanvas', 'PUT failed', err);
    }
  }, []);

  // Initial GET.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/outer-canvas`);
        if (cancelled) return;
        if (!res.ok) { setLoading(false); return; }
        const body = await res.json();
        if (cancelled) return;
        if (body && isOuterCanvasState(body.state)) {
          setState(body.state);
        } else {
          // Either explicit null or invalid shape — fall through to migration.
          setState(null);
        }
        setLoading(false);
      } catch (err) {
        debug.warn('OuterCanvas', 'GET failed', err);
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // One-shot migration. Runs after the GET resolves to null AND notes have
  // loaded AND the flag is unset.
  useEffect(() => {
    if (loading) return;
    if (state !== null) return;
    if (didMigrate.current) return;

    const flagSet = typeof localStorage !== 'undefined'
      && localStorage.getItem(MIGRATION_FLAG) === 'done';
    if (flagSet) {
      // Flag set but no state — could happen if the server's row was wiped.
      // Treat as "create empty canvas" rather than re-migrating, which would
      // duplicate cards once reconciliation runs.
      const empty = emptyOuterCanvasState();
      didMigrate.current = true;
      setState(empty);
      persist(empty);
      return;
    }

    if (!Array.isArray(notes)) return; // wait until notes hook resolves
    didMigrate.current = true;
    const migrated = migrateLegacyToOuterCanvas({
      notes, groups: groups || [], overlay,
    });
    setState(migrated);
    try { localStorage.setItem(MIGRATION_FLAG, 'done'); }
    catch (err) { debug.warn('OuterCanvas', 'flag persist failed', err); }
    persist(migrated);
  }, [loading, state, notes, groups, overlay, persist]);

  // Reconcile state.noteCards with the live notes array.
  useEffect(() => {
    if (!state) return;
    if (!Array.isArray(notes)) return;
    const noteIds = new Set(notes.map((n) => n.id));
    const cardNoteIds = new Set(state.noteCards.map((c) => c.noteId));
    const missing = notes.filter((n) => !cardNoteIds.has(n.id));
    const orphans = state.noteCards.filter((c) => !noteIds.has(c.noteId));
    if (missing.length === 0 && orphans.length === 0) return;

    const PER_ROW = 4;
    const W = 240; const H = 160; const GAP = 16;
    const baseY = state.noteCards.reduce(
      (m, c) => Math.max(m, c.position.y + c.size.h), 0) + GAP;
    const additions = missing.map((n, i) => createNoteCard({
      noteId: n.id,
      pinned: overlay.isPinned(n.id),
      tags: overlay.getUserTags(n.id),
      archived: overlay.isTrashed(n.id),
      position: {
        x: (i % PER_ROW) * (W + GAP),
        y: baseY + Math.floor(i / PER_ROW) * (H + GAP),
      },
    }));
    const next = {
      ...state,
      noteCards: [
        ...state.noteCards.filter((c) => noteIds.has(c.noteId)),
        ...additions,
      ],
    };
    setState(next);
    persist(next);
  }, [notes, state, overlay, persist]);

  const commit = useCallback(async (next) => {
    setState(next);
    await persist(next);
  }, [persist]);

  return { state, loading, commit };
}
