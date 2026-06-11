import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  applyNodeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  IconChevronLeft,
  IconTrash,
  IconPin,
  IconRestore,
  IconArchive,
} from './Icons';
import { debug } from '../lib/debug';
import NoteMenu from './NoteMenu';
import TagEditor from './TagEditor';
import useMicRecorder from '../hooks/useMicRecorder';
import TextCard from './cards/TextCard.jsx';
import {
  innerStateFromNote,
  applyTextEdit,
  applyNodePosition,
  stateToReactFlowNodes,
} from '../lib/canvas/cardState.js';
import {
  DICTATION_MODE,
  HOTKEY_LABEL,
  pickDictationMode,
  sayConfirmation,
} from '../lib/dictation-modifiers';

const API_URL = 'http://localhost:8765';

// Define nodeTypes outside the component so the reference is stable
// across renders. React Flow re-validates types on identity change
// and re-mounts every node when types change — performance-critical.
const NODE_TYPES = {
  text: TextCard,
};

function formatFull(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/**
 * Inner canvas view for a single note. Replaces the document-style
 * NoteView. Holds one TextCard primitive in sub-project 1; frames,
 * media, connectors, and link cards land in sub-project 2.
 *
 * Read path: derive InnerCanvasState from note.canvas_state if valid,
 * otherwise fall back to a one-TextCard state derived from note.content
 * (the same shape the migration writes — so post-migration is identical
 * to pre-migration).
 *
 * Write path: every text edit and every node position change updates
 * local state immediately and fires onUpdateNote(id, {canvas_state}).
 * Debounced 600 ms so a drag isn't 60 PUTs.
 */
export default function InnerCanvas({
  note,
  onBack,
  onDeletePermanently,
  overlay,
  startInEdit = false,
  onEditConsumed = () => {},
  onUpdateNote,
  onMoveToGroup,
  previewMode = false,
}) {
  // Title editing
  const titleInputRef = useRef(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');

  // Inner canvas state — initialized from note, updated locally, persisted
  // via debounced onUpdateNote.
  const [canvasState, setCanvasState] = useState(() => innerStateFromNote(note));
  const saveTimeoutRef = useRef(null);
  const editingCardsRef = useRef(new Set());

  // Dictation panel state (sub-project 4 model: mic is always armed in
  // rewrite mode; verbatim survives as a modifier via Shift+Ctrl+Space
  // or a "quote:"/"verbatim:" voice prefix). The mode chosen at press-
  // time lives on a ref so stopAndUpload reads the right value without
  // forcing the keydown handler to re-bind on every change.
  const [isUploading, setIsUploading] = useState(false);
  const [dictationError, setDictationError] = useState(null);
  const dictationModeRef = useRef(DICTATION_MODE.REWRITE);
  const mic = useMicRecorder();

  // Re-derive when the note changes (e.g. WS pushed an update from
  // the server, or user opened a different note).
  useEffect(() => {
    setCanvasState(innerStateFromNote(note));
    setEditingTitle(false);
    setTitleDraft('');
    setIsUploading(false);
    setDictationError(null);
    dictationModeRef.current = DICTATION_MODE.REWRITE;
    editingCardsRef.current.clear();
  }, [note?.id, note?.canvas_state, note?.content]);

  // Cleanup the save timer on unmount so a half-debounced edit doesn't
  // fire after the component is gone.
  useEffect(() => () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
  }, []);

  const scheduleSave = useCallback((next) => {
    if (!note?.id || !onUpdateNote) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      onUpdateNote(note.id, { canvas_state: next });
      saveTimeoutRef.current = null;
    }, 600);
  }, [note?.id, onUpdateNote]);

  const handleNodesChange = useCallback((changes) => {
    setCanvasState((prev) => {
      const prevNodes = stateToReactFlowNodes(prev);
      const nextNodes = applyNodeChanges(changes, prevNodes);
      let next = prev;
      for (const node of nextNodes) {
        const prevNode = prevNodes.find((n) => n.id === node.id);
        if (!prevNode) continue;
        if (prevNode.position.x !== node.position.x
            || prevNode.position.y !== node.position.y) {
          next = applyNodePosition(next, node.id, node.position);
        }
      }
      if (next !== prev) scheduleSave(next);
      return next;
    });
  }, [scheduleSave]);

  const handleCommitMarkdown = useCallback((cardId, markdown) => {
    setCanvasState((prev) => {
      const next = applyTextEdit(prev, cardId, markdown);
      if (next !== prev) scheduleSave(next);
      return next;
    });
  }, [scheduleSave]);

  const handleEditingChange = useCallback((cardId, isEditing) => {
    const set = editingCardsRef.current;
    if (isEditing) set.add(cardId); else set.delete(cardId);
  }, []);

  // Inject the callbacks into each node's `data` object so React Flow
  // passes them to the custom node component. `draggable: false` flips
  // off when a card is in edit mode so the textarea works.
  const nodes = useMemo(() => {
    const base = stateToReactFlowNodes(canvasState);
    return base.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onCommitMarkdown: handleCommitMarkdown,
        onEditingChange: handleEditingChange,
      },
      draggable: !editingCardsRef.current.has(node.id),
    }));
  }, [canvasState, handleCommitMarkdown, handleEditingChange]);

  // -------- Title editing (lifted from NoteView) -------------------

  const beginEdit = useCallback(() => {
    setTitleDraft(note?.title || 'Untitled Note');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 10);
  }, [note?.title]);

  const commitEdit = useCallback(() => {
    const trimmed = titleDraft.trim();
    setEditingTitle(false);
    if (!trimmed || !note || trimmed === note.title) return;
    onUpdateNote?.(note.id, { title: trimmed });
  }, [titleDraft, note, onUpdateNote]);

  const cancelEdit = useCallback(() => {
    setEditingTitle(false);
    setTitleDraft('');
  }, []);

  useEffect(() => {
    if (startInEdit) {
      beginEdit();
      onEditConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startInEdit]);

  // -------- Dictation (sub-project 4 model — always-armed mic) -----

  const startDictation = useCallback(async (mode) => {
    if (mic.isRecording || isUploading) return;
    dictationModeRef.current = mode || DICTATION_MODE.REWRITE;
    setDictationError(null);
    const ok = await mic.start();
    if (!ok) {
      setDictationError(mic.error || 'Could not access microphone. Check permissions.');
    }
  }, [mic, isUploading]);

  const stopAndUpload = useCallback(async () => {
    if (!mic.isRecording) return;
    const blob = await mic.stop();
    if (!blob || !note?.id) return;

    const mode = dictationModeRef.current || DICTATION_MODE.REWRITE;

    setIsUploading(true);
    setDictationError(null);
    try {
      const form = new FormData();
      form.append('file', blob, 'dictation.wav');
      form.append('mode', mode);
      // InnerCanvas always lets the server append to note.content and
      // broadcast `note_updated`; useWebSocket → updateNote refreshes us,
      // which re-derives canvasState from the new content. (Inline-edit
      // injection lands when sub-project 6's structure-aware placement
      // ships — it'll insert into the matching frame instead.)
      form.append('append', 'true');
      form.append('note_id', note.id);

      const res = await fetch(`${API_URL}/transcribe-push-to-talk`, {
        method: 'POST', body: form,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setDictationError(detail?.detail || `Transcription failed (${res.status})`);
        return;
      }

      // Fire-and-forget hear-back so hands-free use confirms the save
      // without needing to look at the screen.
      sayConfirmation(note.title || 'note');
    } catch (err) {
      debug.error('Dictation', 'upload failed', err);
      setDictationError('Network error — is the Python service running?');
    } finally {
      setIsUploading(false);
    }
  }, [mic, note?.id, note?.title]);

  const cancelDictation = useCallback(async () => {
    if (mic.isRecording) await mic.stop();
    setDictationError(null);
  }, [mic]);

  // Push-to-talk hotkeys: Ctrl+Space = rewrite, Shift+Ctrl+Space = verbatim.
  // Suppressed while a text field has focus so plain typing still works.
  // Always live (no per-note arm/disarm) since the mode-picker is gone.
  useEffect(() => {
    const isInTextField = () => {
      const el = document.activeElement;
      if (!el) return false;
      const tag = el.tagName;
      return (
        tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable === true
      );
    };

    let downActive = false;

    const onDown = (e) => {
      const mode = pickDictationMode(e);
      if (!mode) return;
      if (isInTextField()) return;
      if (downActive) return; // ignore key auto-repeat
      e.preventDefault();
      downActive = true;
      startDictation(mode);
    };

    const onUp = (e) => {
      if (e.code !== 'Space') return;
      if (!downActive) return;
      e.preventDefault();
      downActive = false;
      stopAndUpload();
    };

    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
    };
  }, [startDictation, stopAndUpload]);

  // -------- Render --------------------------------------------------

  if (!note) return null;

  const displayTitle = note.title || 'Untitled Note';
  const isPinned = overlay.isPinned(note.id);
  const isTrashed = overlay.isTrashed(note.id);
  const userTags = overlay.getUserTags(note.id);
  const dateLabel = formatFull(note.created_at);

  // previewMode: skip the React Flow tree (it needs ResizeObserver + DOM).
  // Lay cards out vertically so renderToStaticMarkup produces stable HTML.
  const renderCardsPreview = () => (
    <div className="ic-canvas-preview">
      {canvasState.cards.map((card) => (
        <TextCard
          key={card.id}
          id={card.id}
          data={card.data}
          isPreview
        />
      ))}
    </div>
  );

  const renderCanvas = () => (
    <ReactFlowProvider>
      <ReactFlow
        nodes={nodes}
        edges={[]}
        onNodesChange={handleNodesChange}
        nodeTypes={NODE_TYPES}
        defaultViewport={canvasState.viewport}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesConnectable={false}
        elementsSelectable
      >
        <Background gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </ReactFlowProvider>
  );

  return (
    <div className="ic-note-view">
      <div className="ic-rail">
        <button className="ic-back" onClick={onBack}>
          <IconChevronLeft size={14} stroke={1.5} />
          <span>All notes</span>
        </button>
        <div className="ic-rail-spacer" />
        {isPinned && (
          <span className="tag-chip pinned-chip" title="Pinned">
            <IconPin size={10} stroke={1.6} filled /> PINNED
          </span>
        )}
        <span className="ic-rail-date">{dateLabel}</span>
        <div className="ic-rail-actions">
          {!isTrashed && (
            <>
              <button
                className={`icon-btn md ${isPinned ? 'active' : ''}`}
                onClick={() => overlay.togglePinned(note.id)}
                title={isPinned ? 'Unpin' : 'Pin'}
                aria-label={isPinned ? 'Unpin note' : 'Pin note'}
              >
                <IconPin size={16} stroke={1.5} filled={isPinned} />
              </button>
              <button
                className="icon-btn md"
                onClick={() => { overlay.trashNote(note.id); onBack(); }}
                title="Archive"
                aria-label="Archive note"
              >
                <IconArchive size={16} stroke={1.5} />
              </button>
            </>
          )}
          {isTrashed && (
            <>
              <button
                className="icon-btn md"
                onClick={() => overlay.restoreNote(note.id)}
                title="Restore"
                aria-label="Restore note"
              >
                <IconRestore size={16} stroke={1.5} />
              </button>
              <button
                className="icon-btn md danger"
                onClick={() => onDeletePermanently(note.id)}
                title="Delete permanently"
                aria-label="Delete note permanently"
              >
                <IconTrash size={16} stroke={1.5} />
              </button>
            </>
          )}
          <NoteMenu
            isPinned={isPinned}
            isTrashed={isTrashed}
            onPin={() => overlay.togglePinned(note.id)}
            onEdit={beginEdit}
            onTrash={() => { overlay.trashNote(note.id); onBack(); }}
            onRestore={() => overlay.restoreNote(note.id)}
            onDeletePermanently={() => onDeletePermanently(note.id)}
            onMoveToGroup={onMoveToGroup}
            size="md"
            align="right"
          />
        </div>
      </div>

      <div className="ic-header">
        {editingTitle ? (
          <input
            ref={titleInputRef}
            className="ic-title-input"
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); commitEdit(); }
              if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
            }}
            maxLength={200}
          />
        ) : (
          <h1
            className="ic-title"
            onDoubleClick={beginEdit}
            title="Double-click to rename"
          >
            {displayTitle}
          </h1>
        )}
        <div className="ic-tags">
          <TagEditor
            tags={userTags}
            onAdd={(t) => overlay.addUserTag(note.id, t)}
            onRemove={(t) => overlay.removeUserTag(note.id, t)}
          />
        </div>

        {!isTrashed && (
          <div className="ic-dictation dictation-panel">
            <button
              type="button"
              className={`dictation-mic-btn ${mic.isRecording ? 'recording' : ''}`}
              onMouseDown={() => startDictation(DICTATION_MODE.REWRITE)}
              onMouseUp={stopAndUpload}
              onMouseLeave={mic.isRecording ? stopAndUpload : undefined}
              onTouchStart={(e) => { e.preventDefault(); startDictation(DICTATION_MODE.REWRITE); }}
              onTouchEnd={(e) => { e.preventDefault(); stopAndUpload(); }}
              disabled={isUploading}
              aria-label="Hold to dictate (AI Rewrite). Hold Shift for verbatim."
              title={`${HOTKEY_LABEL.REWRITE} for AI Rewrite · ${HOTKEY_LABEL.VERBATIM} for verbatim`}
            >
              <span className="dictation-mic-dot" />
              <span className="dictation-mic-label">
                {mic.isRecording
                  ? `Recording… (${dictationModeRef.current}) release to insert`
                  : isUploading
                    ? 'Transcribing…'
                    : `Hold ${HOTKEY_LABEL.REWRITE} or this button`}
              </span>
            </button>
            {mic.isRecording && (
              <button
                type="button"
                className="dictation-cancel"
                onClick={cancelDictation}
                title="Discard this recording"
              >
                Cancel
              </button>
            )}
            {dictationError && <span className="dictation-error">{dictationError}</span>}
          </div>
        )}
      </div>

      <div className="ic-surface">
        {previewMode ? renderCardsPreview() : renderCanvas()}
      </div>
    </div>
  );
}
