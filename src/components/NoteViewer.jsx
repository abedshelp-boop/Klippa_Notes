import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';

export default function NoteViewer({ note, onDelete }) {
  if (!note) {
    return (
      <div className="viewer-panel">
        <div className="viewer-empty">
          <div className="viewer-empty-icon">D</div>
          <div className="viewer-empty-text">No note selected</div>
          <div className="viewer-empty-hint">
            Select a note from the sidebar or say "Hey Deen" to create one
          </div>
        </div>
      </div>
    );
  }

  const tags = note.tags ? (typeof note.tags === 'string' ? JSON.parse(note.tags) : note.tags) : [];
  const createdAt = new Date(note.created_at).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="viewer-panel">
      <div className="viewer-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div className="viewer-title">{note.title || 'Untitled Note'}</div>
          {onDelete && (
            <button
              className="btn btn-ghost"
              style={{ fontSize: '12px', padding: '6px 12px', flexShrink: 0 }}
              onClick={() => onDelete(note.id)}
            >
              Delete
            </button>
          )}
        </div>
        <div className="viewer-meta">
          <span>{createdAt}</span>
          {note.source && <span>Source: {note.source}</span>}
        </div>
        {tags.length > 0 && (
          <div className="viewer-tags">
            {tags.map((tag) => (
              <span key={tag} className="viewer-tag">{tag}</span>
            ))}
          </div>
        )}
      </div>

      <div className="viewer-content">
        <div className="markdown-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeHighlight]}
          >
            {note.content || ''}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
