import React from 'react';

function formatDate(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function extractPreview(content) {
  const lines = content.split('\n').filter((l) => l.trim() && !l.startsWith('#') && !l.startsWith('---'));
  const preview = lines.slice(0, 2).join(' ').replace(/[*_>`#\[\]]/g, '').trim();
  return preview.slice(0, 120) || 'No preview available';
}

export default function NoteCard({ note, isActive, onClick }) {
  const tags = note.tags ? (typeof note.tags === 'string' ? JSON.parse(note.tags) : note.tags) : [];

  return (
    <div className={`note-card ${isActive ? 'active' : ''}`} onClick={onClick}>
      <div className="note-card-title">{note.title || 'Untitled Note'}</div>
      <div className="note-card-preview">{extractPreview(note.content || '')}</div>
      <div className="note-card-meta">
        <span>{formatDate(note.created_at)}</span>
        {tags.slice(0, 3).map((tag) => (
          <span key={tag} className="note-card-tag">{tag}</span>
        ))}
      </div>
    </div>
  );
}
