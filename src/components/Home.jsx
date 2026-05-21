import React, { useMemo, useRef, useState } from 'react';
import { IconArrowRight, IconPin, IconTrash, IconRestore, IconArchive } from './Icons';
import NoteMenu from './NoteMenu';

function formatRelative(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();
  if (sameDay) {
    const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    return `Today · ${time}`;
  }
  if (isYesterday) return 'Yesterday';
  const within7 = (now - date) / 86400000 < 7;
  if (within7) return date.toLocaleDateString('en-US', { weekday: 'short' });
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function extractSubtitle(content) {
  if (!content) return '';
  const lines = content.split('\n').map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (l.startsWith('#')) continue;
    if (l.startsWith('---')) continue;
    if (l.startsWith('>')) continue;
    if (l.startsWith('-') || l.startsWith('*')) {
      return l.replace(/^[-*]\s*\[.\]\s*/, '').replace(/^[-*]\s*/, '').slice(0, 160);
    }
    return l.replace(/[*_`#>]/g, '').slice(0, 160);
  }
  return '';
}

function countWords(content) {
  if (!content) return 0;
  return content.trim().split(/\s+/).filter(Boolean).length;
}

function countBlocks(content) {
  if (!content) return 0;
  return content.split(/\n\s*\n/).filter((b) => b.trim()).length;
}

function NoteCard({
  note,
  idx,
  onOpen,
  isPinned,
  isTrashed,
  userTags,
  titleOverride,
  onTogglePin,
  onTrash,
  onRestore,
  onDeletePermanently,
  onEdit,
  onMoveToGroup,
  onRenameInline,
}) {
  const displayTitle = titleOverride || note.title || 'Untitled Note';
  const subtitle = note.subtitle || extractSubtitle(note.content);
  const wordCount = note.word_count ?? countWords(note.content);
  const blockCount = note.block_count ?? countBlocks(note.content);
  const dateLabel = formatRelative(note.created_at || note.updated_at);

  // Phase 11: inline rename on title double-click.
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef(null);

  const startRename = (e) => {
    if (!onRenameInline) return;
    e.stopPropagation();
    setDraft(displayTitle);
    setRenaming(true);
    setTimeout(() => inputRef.current?.select(), 10);
  };

  const commitRename = () => {
    const trimmed = draft.trim();
    setRenaming(false);
    if (!trimmed || trimmed === note.title) return;
    onRenameInline?.(note.id, trimmed);
  };

  return (
    <div
      className={`note-card ${isTrashed ? 'archived' : ''}`}
      onClick={() => onOpen(note.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onOpen(note.id); }}
    >
      <div className="note-card-top">
        <span className="note-card-index">{String(idx + 1).padStart(3, '0')}</span>
        {isPinned && (
          <span className="note-card-pin-indicator" title="Pinned">
            <IconPin size={10} stroke={1.6} filled />
          </span>
        )}
        {userTags.length > 0 && userTags.slice(0, 2).map((t) => (
          <span key={t} className="tag-chip">{t}</span>
        ))}
        <span className="note-card-date">{dateLabel}</span>
      </div>

      {renaming ? (
        <input
          ref={inputRef}
          className="note-card-title note-card-title-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          onBlur={commitRename}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
            if (e.key === 'Escape') { e.preventDefault(); setRenaming(false); }
          }}
          maxLength={200}
        />
      ) : (
        <div
          className="note-card-title"
          onDoubleClick={startRename}
          title={onRenameInline ? 'Double-click to rename' : undefined}
        >
          {displayTitle}
        </div>
      )}
      <div className="note-card-subtitle">{subtitle || 'No preview available'}</div>

      <div className="note-card-footer">
        <span className="note-card-stats">
          {wordCount} WORDS · {blockCount} BLOCK{blockCount === 1 ? '' : 'S'}
        </span>
        <div className="note-card-actions" onClick={(e) => e.stopPropagation()}>
          {!isTrashed && (
            <>
              <button
                className={`icon-btn sm ${isPinned ? 'active' : ''}`}
                onClick={onTogglePin}
                title={isPinned ? 'Unpin' : 'Pin'}
                aria-label={isPinned ? 'Unpin note' : 'Pin note'}
              >
                <IconPin size={14} stroke={1.6} filled={isPinned} />
              </button>
              <button
                className="icon-btn sm"
                onClick={onTrash}
                title="Archive"
                aria-label="Archive note"
              >
                <IconArchive size={14} stroke={1.6} />
              </button>
            </>
          )}
          {isTrashed && (
            <>
              <button
                className="icon-btn sm"
                onClick={onRestore}
                title="Restore"
                aria-label="Restore note"
              >
                <IconRestore size={14} stroke={1.6} />
              </button>
              <button
                className="icon-btn sm danger"
                onClick={onDeletePermanently}
                title="Delete permanently"
                aria-label="Delete note permanently"
              >
                <IconTrash size={14} stroke={1.6} />
              </button>
            </>
          )}
          <NoteMenu
            isPinned={isPinned}
            isTrashed={isTrashed}
            onPin={onTogglePin}
            onEdit={onEdit}
            onTrash={onTrash}
            onRestore={onRestore}
            onDeletePermanently={onDeletePermanently}
            onMoveToGroup={onMoveToGroup}
            size="sm"
            align="right"
          />
        </div>
        <span className="note-card-arrow"><IconArrowRight size={14} stroke={1.4} /></span>
      </div>
    </div>
  );
}

function buildHeadline(notes, filter) {
  if (filter.type === 'pinned') {
    return {
      main: `${notes.length} pinned note${notes.length === 1 ? '' : 's'}.`,
      accent: notes.length === 0 ? 'Pin a note from its menu to keep it here.' : 'Kept close at hand.',
    };
  }
  if (filter.type === 'archive') {
    return {
      main: `${notes.length} note${notes.length === 1 ? '' : 's'} in archive.`,
      accent: notes.length === 0 ? 'Nothing archived yet.' : 'Restore or delete them for good.',
    };
  }
  if (!notes || notes.length === 0) {
    return {
      main: 'No notes yet.',
      accent: 'Say "Hey Deen" to capture the first one.',
    };
  }
  const weekAgo = Date.now() - 7 * 86400000;
  const thisWeek = notes.filter((n) => {
    const t = new Date(n.created_at || n.updated_at).getTime();
    return !isNaN(t) && t >= weekAgo;
  }).length;
  if (thisWeek === 0) {
    return {
      main: `${notes.length} note${notes.length === 1 ? '' : 's'} in the library.`,
      accent: 'A quiet week — say "Hey Deen" to add another.',
    };
  }
  return {
    main: `${thisWeek} note${thisWeek === 1 ? '' : 's'} this week.`,
    accent: 'Most of them were spoken.',
  };
}

export default function Home({
  notes,
  filter,
  onFilterChange,
  onOpenNote,
  overlay,
  onEditNote,
  onDeletePermanently,
  onCreateNote,
  onMoveToGroup,
  onRenameNote,
}) {
  const allTags = useMemo(() => {
    const counts = new Map();
    for (const n of notes) {
      const t = overlay.getUserTags(n.id);
      for (const tag of t) counts.set(tag, (counts.get(tag) || 0) + 1);
    }
    return Array.from(counts.keys());
  }, [notes, overlay]);

  const tabs = ['All', ...allTags.slice(0, 8)];
  const activeTab = filter.type === 'tag' ? filter.value : 'All';
  const showFilterTabs = filter.type !== 'archive' && filter.type !== 'pinned';

  const visible = useMemo(() => {
    const pinnedFirst = (a, b) => {
      const pa = overlay.isPinned(a.id) ? 1 : 0;
      const pb = overlay.isPinned(b.id) ? 1 : 0;
      return pb - pa;
    };
    return [...notes].sort(pinnedFirst);
  }, [notes, overlay]);

  const headline = useMemo(() => buildHeadline(visible, filter), [visible, filter]);
  const today = new Date();
  const yearLabel = today.getFullYear();

  const setTab = (t) => {
    if (t === 'All') onFilterChange({ type: 'all' });
    else onFilterChange({ type: 'tag', value: t });
  };

  const eyebrowLabel =
    filter.type === 'pinned' ? 'DEEN · PINNED' :
    filter.type === 'archive' ? 'DEEN · ARCHIVE' :
    filter.type === 'tag' ? `DEEN · #${filter.value.toUpperCase()}` :
    `DEEN · NOTES · ${yearLabel}`;

  return (
    <div className="home">
      <div className="home-hero">
        <div className="home-eyebrow">{eyebrowLabel}</div>
        <div className="home-headline">
          {headline.main}<br />
          <em>{headline.accent}</em>
        </div>
        {filter.type !== 'archive' && (
          <div className="home-subhead">
            <span>
              Say <span className="kbd">"Hey Deen"</span> to start dictating, or
            </span>
            {onCreateNote && (
              <button
                type="button"
                className="home-new-note-btn"
                onClick={onCreateNote}
              >
                + Write a new note
              </button>
            )}
          </div>
        )}
      </div>

      {showFilterTabs && tabs.length > 1 && (
        <div className="filter-tabs">
          {tabs.map((t) => (
            <button
              key={t}
              className={`filter-tab ${activeTab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {visible.length === 0 ? (
        <div className="home-empty">
          <div>
            {filter.type === 'pinned' ? 'No pinned notes.' :
             filter.type === 'archive' ? 'Archive is empty.' :
             filter.type === 'tag' ? `No notes tagged #${filter.value}.` :
             'Nothing here yet.'}
          </div>
          {filter.type !== 'archive' && (
            <div className="home-empty-hint">Press Ctrl+Shift+N or say "Hey Deen"</div>
          )}
        </div>
      ) : (
        <div className="rise-in notes-grid">
          {visible.map((n, i) => (
            <NoteCard
              key={n.id}
              note={n}
              idx={i}
              onOpen={onOpenNote}
              isPinned={overlay.isPinned(n.id)}
              isTrashed={overlay.isTrashed(n.id)}
              userTags={overlay.getUserTags(n.id)}
              titleOverride={overlay.getTitleOverride(n.id)}
              onTogglePin={() => overlay.togglePinned(n.id)}
              onTrash={() => overlay.trashNote(n.id)}
              onRestore={() => overlay.restoreNote(n.id)}
              onDeletePermanently={() => onDeletePermanently(n.id)}
              onEdit={() => onEditNote(n.id)}
              onMoveToGroup={onMoveToGroup ? () => onMoveToGroup(n.id) : undefined}
              onRenameInline={onRenameNote}
            />
          ))}
        </div>
      )}

      {visible.length > 0 && (
        <div className="home-footer">· end of notes ·</div>
      )}
    </div>
  );
}
