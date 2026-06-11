import React, { useEffect, useState } from 'react';
import {
  IconInbox,
  IconStar,
  IconArchive,
  IconHash,
} from './Icons';
import GroupTree from './GroupTree';
import logoUrl from '../../assets/logo.svg';

const STATUS_LABELS = {
  listening: 'MIC READY · EN-US',
  command: 'LISTENING · COMMAND',
  processing: 'PROCESSING',
  error: 'CONNECTION ERROR',
  disconnected: 'CONNECTING...',
};

export default function Sidebar({
  notes,
  filter,
  onFilterChange,
  onListen,
  onOpenNote,
  onOpenSettings,
  status,
  capturing,
  overlay,
  onCreateNote,
  groups = [],
  onCreateGroup,
  onRenameGroup,
  onDeleteGroup,
}) {
  // Sub-project 5: the Quick Inbox is a permanent, always-there note. Surface
  // it as a pinned row at the top of the library (hidden in archive view).
  const quickInbox = notes.find((n) => n.is_quick_inbox);
  const ctrlKey = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform) ? '⌘' : 'Ctrl';

  const nonTrashedCount = notes.filter((n) => !overlay.isTrashed(n.id)).length;
  const pinnedCount = notes.filter((n) => overlay.isPinned(n.id) && !overlay.isTrashed(n.id)).length;
  const archivedCount = notes.filter((n) => overlay.isTrashed(n.id)).length;

  const [bubbleVisible, setBubbleVisible] = useState(true);
  const [bubbleApiAvailable, setBubbleApiAvailable] = useState(false);

  useEffect(() => {
    const api = window.electronAPI;
    if (!api?.getBubbleVisible) return;
    setBubbleApiAvailable(true);
    api.getBubbleVisible().then((v) => {
      if (typeof v === 'boolean') setBubbleVisible(v);
    }).catch(() => {});
    const unsubscribe = api.onBubbleVisibilityChange?.((v) => {
      if (typeof v === 'boolean') setBubbleVisible(v);
    });
    return unsubscribe;
  }, []);

  const toggleBubble = async () => {
    const api = window.electronAPI;
    if (!api?.setBubbleVisible) return;
    const next = !bubbleVisible;
    setBubbleVisible(next);
    try {
      const result = await api.setBubbleVisible(next);
      if (typeof result === 'boolean') setBubbleVisible(result);
    } catch {
      setBubbleVisible(!next);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={logoUrl} className="brand-orb" alt="" draggable={false} />
        <div>
          <div className="brand-text-main">Deen<em>-notes</em></div>
          <div className="brand-text-sub">V 1.0 · {status === 'disconnected' || status === 'error' ? 'OFFLINE' : 'ONLINE'}</div>
        </div>
      </div>

      <button
        className="listen-cta"
        onClick={onListen}
        disabled={capturing}
      >
        <span className="listen-cta-dot" />
        <span className="listen-cta-label">
          {capturing ? 'Listening...' : 'Say "Hey Deen"'}
        </span>
        <span className="kbd">{ctrlKey} D</span>
      </button>

      {onCreateNote && (
        <button
          className="sidebar-new-note"
          onClick={onCreateNote}
          title="Create a new empty note"
        >
          <span className="sidebar-new-note-icon">+</span>
          <span className="sidebar-new-note-label">New note</span>
        </button>
      )}

      {quickInbox && filter.type !== 'archive' && (
        <button
          className="sidebar-quick-inbox"
          onClick={() => onOpenNote?.(quickInbox.id)}
          title="Quick Inbox — voice captures with no destination land here"
        >
          <span className="sidebar-quick-inbox-icon">📥</span>
          <span className="sidebar-quick-inbox-label">Quick Inbox</span>
        </button>
      )}

      <div className="sidebar-header">Library</div>
      <button
        className={`sidebar-item ${filter.type === 'all' ? 'active' : ''}`}
        onClick={() => onFilterChange({ type: 'all' })}
      >
        <span className="sidebar-item-icon"><IconInbox /></span>
        <span className="sidebar-item-label">All notes</span>
        <span className="sidebar-item-count">{nonTrashedCount}</span>
      </button>
      <button
        className={`sidebar-item ${filter.type === 'pinned' ? 'active' : ''}`}
        onClick={() => onFilterChange({ type: 'pinned' })}
      >
        <span className="sidebar-item-icon"><IconStar /></span>
        <span className="sidebar-item-label">Pinned</span>
        <span className="sidebar-item-count">{pinnedCount}</span>
      </button>
      <button
        className={`sidebar-item ${filter.type === 'archive' ? 'active' : ''}`}
        onClick={() => onFilterChange({ type: 'archive' })}
      >
        <span className="sidebar-item-icon"><IconArchive /></span>
        <span className="sidebar-item-label">Archive</span>
        <span className="sidebar-item-count">{archivedCount}</span>
      </button>

      <div className="sidebar-header sidebar-header-row">
        <span>Groups</span>
        {onCreateGroup && (
          <button
            type="button"
            className="sidebar-header-btn"
            onClick={async () => {
              const name = window.prompt('New group name', '');
              if (name && name.trim()) await onCreateGroup(name.trim(), null);
            }}
            title="Create a new top-level group"
            aria-label="Create group"
          >
            +
          </button>
        )}
      </div>

      <GroupTree
        groups={groups}
        notes={notes}
        activeGroupId={filter.type === 'group' ? filter.value : null}
        onSelectGroup={(id) => onFilterChange({ type: 'group', value: id })}
        onCreateGroup={onCreateGroup}
        onRenameGroup={onRenameGroup}
        onDeleteGroup={onDeleteGroup}
      />

      {overlay.allUserTags.length > 0 && (
        <>
          <div className="sidebar-header">Tags</div>
          {overlay.allUserTags.slice(0, 12).map(([tag, count]) => (
            <button
              key={tag}
              className={`sidebar-item ${filter.type === 'tag' && filter.value === tag ? 'active' : ''}`}
              onClick={() => onFilterChange({ type: 'tag', value: tag })}
            >
              <span className="sidebar-item-icon"><IconHash /></span>
              <span className="sidebar-item-label">{tag}</span>
              <span className="sidebar-item-count">{count}</span>
            </button>
          ))}
        </>
      )}

      <div style={{ flex: 1 }} />

      <div className="sidebar-footer">
        <div className="sidebar-status">
          <span className={`sidebar-status-dot ${status}`} />
          <span>{STATUS_LABELS[status] || 'UNKNOWN'}</span>
        </div>

        {bubbleApiAvailable && (
          <button
            className={`sidebar-bubble-toggle ${bubbleVisible ? 'on' : 'off'}`}
            onClick={toggleBubble}
            aria-pressed={bubbleVisible}
            title={bubbleVisible ? 'Hide desktop bubble' : 'Show desktop bubble'}
          >
            <span className="sidebar-bubble-toggle-dot" />
            <span className="sidebar-bubble-toggle-label">Desktop bubble</span>
            <span className="sidebar-bubble-toggle-state">
              {bubbleVisible ? 'ON' : 'OFF'}
            </span>
          </button>
        )}

        <button className="sidebar-settings-btn" onClick={onOpenSettings}>
          Settings
        </button>
      </div>
    </aside>
  );
}
