import React from 'react';

const STATUS_LABELS = {
  listening: 'Listening for "Hey Klippa" — or press Ctrl+Shift+N',
  command: 'Heard you! Tell me what to note down...',
  processing: 'Processing your note...',
  error: 'Connection error',
  disconnected: 'Connecting to service...',
};

export default function StatusBar({ status, noteCount }) {
  return (
    <div className="status-bar">
      <div className="status-indicator">
        <div className={`status-dot ${status}`} />
        <span>{STATUS_LABELS[status] || 'Unknown'}</span>
      </div>
      <span>{noteCount} note{noteCount !== 1 ? 's' : ''}</span>
    </div>
  );
}
