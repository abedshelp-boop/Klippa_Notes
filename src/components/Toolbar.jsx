import React from 'react';
import { IconSearch } from './Icons';
import WindowChrome from './WindowChrome';

export default function Toolbar({ query, onQueryChange }) {
  const ctrlKey = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform) ? '⌘' : 'Ctrl';
  return (
    <div className="toolbar">
      <label className="toolbar-search">
        <span className="toolbar-search-icon"><IconSearch size={14} /></span>
        <input
          className="toolbar-search-input"
          type="text"
          placeholder="Search notes, tags, transcripts"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
        <span className="kbd">{ctrlKey} K</span>
      </label>
      <div className="toolbar-spacer" />
      <WindowChrome />
    </div>
  );
}
