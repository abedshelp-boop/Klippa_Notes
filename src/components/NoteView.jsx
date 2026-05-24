import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
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
import MermaidBlock from './MermaidBlock';
import ChartBlock from './ChartBlock';
import useMicRecorder from '../hooks/useMicRecorder';
import {
  DICTATION_MODE,
  HOTKEY_LABEL,
  pickDictationMode,
  sayConfirmation,
} from '../lib/dictation-modifiers';

const API_URL = 'http://localhost:8765';

/**
 * Phase 8: rehype-sanitize schema that extends the default to allow inline
 * SVG (so the AI can hand-author small diagrams). Uses camelCase hast
 * property names — `viewBox` not `viewbox`, `strokeWidth` not `stroke-width`.
 * Sanitize is an ALLOW-LIST: <script>, <foreignObject>, on* handlers are
 * blocked simply by being absent — no explicit deny rule needed.
 *
 * Mermaid & chart fenced blocks bypass this entirely (handled by the
 * components.code override below, which receives raw fenced text).
 */
const SVG_TAGS = [
  'svg', 'g', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon',
  'text', 'tspan', 'defs', 'clipPath', 'mask', 'linearGradient', 'stop',
  'title', 'desc', 'use', 'symbol',
];
const SVG_ATTRS = [
  'viewBox', 'xmlns', 'd', 'fill', 'stroke', 'strokeWidth', 'strokeLinecap',
  'strokeLinejoin', 'strokeDasharray', 'transform', 'cx', 'cy', 'r',
  'x', 'y', 'x1', 'y1', 'x2', 'y2', 'points', 'width', 'height',
  'opacity', 'fillOpacity', 'strokeOpacity', 'fontSize', 'textAnchor',
  'fontFamily', 'fontWeight',
  'offset', 'stopColor', 'stopOpacity', 'gradientUnits',
  'gradientTransform', 'clipPathUnits', 'href', 'preserveAspectRatio',
];

const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), ...SVG_TAGS],
  attributes: {
    ...defaultSchema.attributes,
    '*': [
      ...(defaultSchema.attributes?.['*'] || []),
      ...SVG_ATTRS,
    ],
  },
};

function formatFull(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function stripLeadingHeading(markdown) {
  if (!markdown) return '';
  const lines = markdown.split('\n');
  let i = 0;
  while (i < lines.length && !lines[i].trim()) i++;
  if (i < lines.length && /^#\s/.test(lines[i].trim())) {
    i++;
    while (i < lines.length && !lines[i].trim()) i++;
  }
  return lines.slice(i).join('\n');
}

export default function NoteView({
  note,
  onBack,
  onDeletePermanently,
  overlay,
  startInEdit = false,
  onEditConsumed,
  onUpdateNote,
  onMoveToGroup,
}) {
  const scrollRef = useRef(null);
  const titleInputRef = useRef(null);
  const bodyTextareaRef = useRef(null);
  const [scrollPct, setScrollPct] = useState(0);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [editingBody, setEditingBody] = useState(false);
  const [bodyDraft, setBodyDraft] = useState('');

  // Sub-project 4: the dictation mic is always armed in rewrite mode.
  // Verbatim survives as a modifier — Shift+Ctrl+Space, or a "quote:" /
  // "verbatim:" voice prefix handled server-side. The ref carries the mode
  // chosen at press-time so stopAndUpload reads the right value without
  // needing the keydown handler to re-bind.
  const [isUploading, setIsUploading] = useState(false);
  const [dictationError, setDictationError] = useState(null);
  const editingBodyRef = useRef(false);
  const bodyDraftRef = useRef('');
  const dictationModeRef = useRef(DICTATION_MODE.REWRITE);
  const mic = useMicRecorder();

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const max = el.scrollHeight - el.clientHeight;
      setScrollPct(max > 0 ? el.scrollTop / max : 0);
    };
    el.scrollTop = 0;
    setScrollPct(0);
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, [note?.id]);

  useEffect(() => {
    setEditingTitle(false);
    setTitleDraft('');
    setEditingBody(false);
    setBodyDraft('');
    setIsUploading(false);
    setDictationError(null);
    dictationModeRef.current = DICTATION_MODE.REWRITE;
  }, [note?.id]);

  // Keep refs in sync so hotkey handlers can read the latest value without
  // being callback dependencies (which would force re-binding).
  useEffect(() => { editingBodyRef.current = editingBody; }, [editingBody]);
  useEffect(() => { bodyDraftRef.current = bodyDraft; }, [bodyDraft]);

  useEffect(() => {
    if (startInEdit) {
      beginEdit();
      beginBodyEdit();
      onEditConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startInEdit]);

  if (!note) return null;

  const isPinned = overlay.isPinned(note.id);
  const isTrashed = overlay.isTrashed(note.id);
  const userTags = overlay.getUserTags(note.id);
  const displayTitle = note.title || 'Untitled Note';
  const dateLabel = formatFull(note.created_at);
  const body = stripLeadingHeading(note.content || '');

  const beginEdit = () => {
    setTitleDraft(displayTitle);
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 10);
  };

  const commitEdit = () => {
    const trimmed = titleDraft.trim();
    setEditingTitle(false);
    if (!trimmed) return;
    if (trimmed === note.title) return; // no-op
    if (onUpdateNote) {
      onUpdateNote(note.id, { title: trimmed });
    }
  };

  const cancelEdit = () => {
    setEditingTitle(false);
    setTitleDraft('');
  };

  const beginBodyEdit = () => {
    setBodyDraft(note.content || '');
    setEditingBody(true);
    setTimeout(() => {
      const el = bodyTextareaRef.current;
      if (el) {
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
      }
    }, 10);
  };

  const commitBodyEdit = () => {
    setEditingBody(false);
    if (bodyDraft === (note.content || '')) return; // no-op
    if (onUpdateNote) {
      onUpdateNote(note.id, { content: bodyDraft });
    }
  };

  const cancelBodyEdit = () => {
    setEditingBody(false);
    setBodyDraft('');
  };

  const handleBodyChange = (e) => {
    setBodyDraft(e.target.value);
    // Auto-resize the textarea.
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  // -------- Sub-project 4: push-to-talk dictation ---------

  const startDictation = useCallback(async (mode) => {
    if (mic.isRecording || isUploading) return;
    dictationModeRef.current = mode || DICTATION_MODE.REWRITE;
    setDictationError(null);
    const ok = await mic.start();
    if (!ok) {
      setDictationError(
        mic.error || 'Could not access microphone. Check permissions.',
      );
    }
  }, [mic, isUploading]);

  const stopAndUpload = useCallback(async () => {
    if (!mic.isRecording) return;
    const blob = await mic.stop();
    if (!blob) {
      // No samples captured — user pressed-and-released too fast.
      return;
    }
    if (!note?.id) return;

    const mode = dictationModeRef.current || DICTATION_MODE.REWRITE;

    setIsUploading(true);
    setDictationError(null);
    try {
      const form = new FormData();
      form.append('file', blob, 'dictation.wav');
      form.append('mode', mode);
      // If the body editor is open we apply locally so the user doesn't
      // lose their in-progress edits; otherwise let the server append and
      // the WS broadcast refresh the note.
      const inBodyEdit = editingBodyRef.current;
      form.append('append', inBodyEdit ? 'false' : 'true');
      if (!inBodyEdit) form.append('note_id', note.id);

      const res = await fetch(`${API_URL}/transcribe-push-to-talk`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setDictationError(detail?.detail || `Transcription failed (${res.status})`);
        return;
      }
      const data = await res.json();
      const polished = (data?.text || '').trim();
      if (!polished) return;

      if (inBodyEdit) {
        // Inject into the open textarea draft.
        const next = bodyDraftRef.current
          ? `${bodyDraftRef.current.replace(/\s+$/, '')}\n\n${polished}`
          : polished;
        setBodyDraft(next);
      }
      // Otherwise the server already appended + broadcast `note_updated`,
      // which the useWebSocket hook routes through handleNoteUpdated →
      // updateNote, refreshing the visible note without us doing anything.

      // Fire-and-forget hear-back so hands-free use confirms the save
      // without needing to look at the screen.
      sayConfirmation(displayTitle);
    } catch (err) {
      debug.error('Dictation', 'upload failed', err);
      setDictationError('Network error — is the Python service running?');
    } finally {
      setIsUploading(false);
    }
  }, [mic, note?.id, displayTitle]);

  const cancelDictation = useCallback(async () => {
    if (mic.isRecording) {
      await mic.stop(); // discard
    }
    setDictationError(null);
  }, [mic]);

  // Push-to-talk hotkeys: Ctrl+Space = rewrite, Shift+Ctrl+Space = verbatim.
  // Suppressed when the title input or body textarea has focus so plain
  // typing still works. Always live now that the mode-picker is gone.
  useEffect(() => {
    const isInTextField = () => {
      const el = document.activeElement;
      if (!el) return false;
      const tag = el.tagName;
      return (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        el.isContentEditable === true
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

  return (
    <div className="note-view">
      <div className="note-view-rail">
        <button className="note-view-back" onClick={onBack}>
          <IconChevronLeft size={14} stroke={1.5} />
          <span>All notes</span>
        </button>
        <div className="note-view-rail-spacer" />
        {isPinned && (
          <span className="tag-chip pinned-chip" title="Pinned">
            <IconPin size={10} stroke={1.6} filled /> PINNED
          </span>
        )}
        <span className="note-view-date">{dateLabel}</span>

        <div className="note-view-actions">
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

      <div className="note-view-progress">
        <div
          className="note-view-progress-bar"
          style={{ width: `${scrollPct * 100}%` }}
        />
      </div>

      <div ref={scrollRef} className="note-view-scroll">
        <div className="note-view-inner">
          {editingTitle ? (
            <input
              ref={titleInputRef}
              className="note-view-title-input"
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
              className="note-view-heading"
              onDoubleClick={beginEdit}
              title="Double-click to rename"
            >
              {displayTitle}
            </h1>
          )}

          <div className="note-view-meta">
            <span>{dateLabel}</span>
            {note.source && <span>· Source: {note.source}</span>}
            {isTrashed && <span className="note-view-meta-archive">· Archived</span>}
          </div>

          <div className="note-view-tags-section">
            <TagEditor
              tags={userTags}
              onAdd={(t) => overlay.addUserTag(note.id, t)}
              onRemove={(t) => overlay.removeUserTag(note.id, t)}
            />
          </div>

          {!isTrashed && (
            <div className="dictation-panel">
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
              {dictationError && (
                <span className="dictation-error">{dictationError}</span>
              )}
            </div>
          )}

          {!isTrashed && (
            <div className="note-view-body-toolbar">
              {editingBody ? (
                <>
                  <button
                    type="button"
                    className="note-view-body-btn primary"
                    onClick={commitBodyEdit}
                    title="Save (or click outside)"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="note-view-body-btn"
                    onClick={cancelBodyEdit}
                    title="Discard changes"
                  >
                    Cancel
                  </button>
                  <span className="note-view-body-hint">
                    Tip: Ctrl+Enter to save, Esc to cancel
                  </span>
                </>
              ) : (
                <button
                  type="button"
                  className="note-view-body-btn"
                  onClick={beginBodyEdit}
                  title="Edit note body"
                >
                  Edit
                </button>
              )}
            </div>
          )}

          {editingBody ? (
            <textarea
              ref={bodyTextareaRef}
              className="note-view-body-editor"
              value={bodyDraft}
              onChange={handleBodyChange}
              onBlur={commitBodyEdit}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  e.preventDefault();
                  commitBodyEdit();
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  cancelBodyEdit();
                }
              }}
              spellCheck={true}
              placeholder="Start typing..."
            />
          ) : (
            <div className="markdown-body rise-in">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                /* Plugin order is load-bearing:
                   1. rehypeRaw — re-parse raw HTML so inline <svg> becomes
                      real hast nodes.
                   2. rehypeKatex / rehypeHighlight — transform math + code
                      into span trees.
                   3. rehypeSanitize LAST — strip everything not in the
                      allow-list, including any DOM-clobbering / on* attrs. */
                rehypePlugins={[
                  rehypeRaw,
                  rehypeKatex,
                  rehypeHighlight,
                  [rehypeSanitize, SANITIZE_SCHEMA],
                ]}
                components={{
                  /* Phase 8: ```mermaid → diagram, ```chart → Recharts.
                     Both receive raw fenced text via children and bypass the
                     rehype-sanitize allow-list (they render React components,
                     not raw HTML). Other code fences fall through to the
                     default <code> + rehype-highlight pipeline. */
                  code({ className, children, ...props }) {
                    const text = String(children || '').replace(/\n$/, '');
                    if (className === 'language-mermaid') {
                      return <MermaidBlock code={text} />;
                    }
                    if (className === 'language-chart') {
                      return <ChartBlock source={text} />;
                    }
                    return <code className={className} {...props}>{children}</code>;
                  },
                }}
              >
                {body}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
