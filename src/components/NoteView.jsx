import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import {
  IconChevronLeft,
  IconTrash,
  IconPin,
  IconRestore,
  IconArchive,
} from './Icons';
import NoteMenu from './NoteMenu';
import TagEditor from './TagEditor';

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
}) {
  const scrollRef = useRef(null);
  const titleInputRef = useRef(null);
  const [scrollPct, setScrollPct] = useState(0);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');

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
  }, [note?.id]);

  useEffect(() => {
    if (startInEdit) {
      beginEdit();
      onEditConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startInEdit]);

  if (!note) return null;

  const isPinned = overlay.isPinned(note.id);
  const isTrashed = overlay.isTrashed(note.id);
  const userTags = overlay.getUserTags(note.id);
  const titleOverride = overlay.getTitleOverride(note.id);
  const displayTitle = titleOverride || note.title || 'Untitled Note';
  const dateLabel = formatFull(note.created_at);
  const body = stripLeadingHeading(note.content || '');

  const beginEdit = () => {
    setTitleDraft(displayTitle);
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 10);
  };

  const commitEdit = () => {
    const trimmed = titleDraft.trim();
    if (trimmed && trimmed !== note.title) {
      overlay.setTitleOverride(note.id, trimmed);
    } else if (!trimmed || trimmed === note.title) {
      overlay.setTitleOverride(note.id, '');
    }
    setEditingTitle(false);
  };

  const cancelEdit = () => {
    setEditingTitle(false);
    setTitleDraft('');
  };

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
              {titleOverride && titleOverride !== note.title && (
                <span className="note-view-renamed" title={`Original: ${note.title}`}>·</span>
              )}
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

          <div className="markdown-body rise-in">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex, rehypeHighlight]}
            >
              {body}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
