import React from 'react';
import { Handle, Position } from '@xyflow/react';

function formatRelative(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric', minute: '2-digit',
    });
  }
  const within7 = (now - date) / 86400000 < 7;
  if (within7) return date.toLocaleDateString('en-US', { weekday: 'short' });
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function extractPreview(content) {
  if (!content) return '';
  const lines = content.split('\n').map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (l.startsWith('#')) continue;
    if (l.startsWith('---')) continue;
    return l.replace(/[*_`#>[\]]/g, '').slice(0, 140);
  }
  return '';
}

/**
 * Custom node rendered for `type: 'note-card'`. React Flow passes us a `data`
 * prop with whatever we put into the node's data.
 *
 * Expected `data` shape:
 *   note: { id, title, content, updated_at, created_at }
 *   pinned, archived: boolean
 *   tags: string[]
 *   onOpen?: (noteId) => void
 */
export default function NoteCardOnCanvas({ data }) {
  const note = data?.note;
  if (!note) return null;
  const title = (note.title || '').trim() || 'Untitled Note';
  const preview = extractPreview(note.content || '') || 'No preview available';
  const dateLabel = formatRelative(note.updated_at || note.created_at);
  const tags = Array.isArray(data.tags) ? data.tags : [];

  const onClick = (e) => {
    // Don't hijack the handle drag interaction.
    if (e.target.closest('.react-flow__handle')) return;
    if (typeof data.onOpen === 'function') data.onOpen(note.id);
  };

  const cls = [
    'oc-card',
    data.pinned ? 'is-pinned' : '',
    data.archived ? 'is-archived' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls} onClick={onClick}>
      <Handle
        type="target"
        position={Position.Top}
        className="oc-card-handle"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="oc-card-handle"
      />

      <div className="oc-card-top">
        {data.pinned && (
          <span
            className="oc-card-pin"
            aria-label="Pinned"
            title="Pinned"
          >●</span>
        )}
        {tags.slice(0, 2).map((t) => (
          <span key={t} className="oc-card-tag">{t}</span>
        ))}
        <span className="oc-card-date">{dateLabel}</span>
      </div>
      <div className="oc-card-title">{title}</div>
      <div className="oc-card-preview">{preview}</div>
    </div>
  );
}
