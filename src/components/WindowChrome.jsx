import React from 'react';

export default function WindowChrome() {
  const api = typeof window !== 'undefined' ? window.electronAPI : null;

  return (
    <div className="window-chrome">
      <button
        className="window-chrome-btn"
        onClick={() => api?.minimize()}
        aria-label="Minimize"
        title="Minimize"
      >
        <svg viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
          <path d="M3 5.5 H8" />
        </svg>
      </button>
      <button
        className="window-chrome-btn"
        onClick={() => api?.maximize()}
        aria-label="Fullscreen"
        title="Fullscreen"
      >
        <svg viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 2.5 H2.5 V4 M8.5 4 V2.5 H7 M2.5 7 V8.5 H4 M7 8.5 H8.5 V7" />
        </svg>
      </button>
      <button
        className="window-chrome-btn"
        onClick={() => api?.close()}
        aria-label="Close"
        title="Close"
      >
        <svg viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
          <path d="M3.5 3.5 L7.5 7.5 M7.5 3.5 L3.5 7.5" />
        </svg>
      </button>
    </div>
  );
}
