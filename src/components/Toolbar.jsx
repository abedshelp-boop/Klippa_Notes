import React from 'react';
import { IconSearch } from './Icons';

export default function Toolbar({ query, onQueryChange, onCreateNote }) {
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
      {onCreateNote && (
        <button
          type="button"
          className="toolbar-new-btn"
          onClick={onCreateNote}
          title="Create a new empty note"
        >
          + New
        </button>
      )}
      {/* Phase 5: WindowChrome moved out of the toolbar — it now floats
          at top:0 right:0 of the viewport. The toolbar pads the right
          edge so search + "+ New" never collide with the chrome. */}
    </div>
  );
}
