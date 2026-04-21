import React, { useState } from 'react';
import { IconX, IconPlus } from './Icons';

export default function TagEditor({ tags, onAdd, onRemove }) {
  const [value, setValue] = useState('');
  const [adding, setAdding] = useState(false);

  const commit = () => {
    const v = value.trim();
    if (v) onAdd(v);
    setValue('');
    setAdding(false);
  };

  const onKey = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      setValue('');
      setAdding(false);
    }
  };

  return (
    <div className="tag-editor">
      {tags.map((t) => (
        <span key={t} className="tag-chip removable">
          <span>{t}</span>
          <button
            className="tag-chip-remove"
            onClick={() => onRemove(t)}
            aria-label={`Remove tag ${t}`}
            title={`Remove ${t}`}
          >
            <IconX size={10} stroke={2} />
          </button>
        </span>
      ))}
      {adding ? (
        <input
          className="tag-input"
          autoFocus
          value={value}
          placeholder="new tag"
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
          maxLength={32}
        />
      ) : (
        <button
          className="tag-add-btn"
          onClick={() => setAdding(true)}
          aria-label="Add tag"
        >
          <IconPlus size={10} stroke={1.8} />
          <span>Add tag</span>
        </button>
      )}
    </div>
  );
}
