import React, { useEffect, useRef, useState } from 'react';
import { IconMore, IconPin, IconEdit, IconTrash, IconRestore, IconArchive, IconFolder } from './Icons';

export default function NoteMenu({
  isPinned,
  isTrashed,
  onPin,
  onEdit,
  onTrash,
  onRestore,
  onDeletePermanently,
  onMoveToGroup,
  align = 'right',
  size = 'sm',
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (!ref.current || !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const close = () => setOpen(false);
  const iconSize = size === 'lg' ? 16 : 14;

  return (
    <div className="note-menu" ref={ref}>
      <button
        className={`icon-btn ${size}`}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        aria-label="Note options"
        aria-expanded={open}
        title="More"
      >
        <IconMore size={iconSize} stroke={2} />
      </button>
      {open && (
        <div
          className={`note-menu-panel ${align}`}
          onClick={(e) => e.stopPropagation()}
        >
          {!isTrashed && (
            <>
              <button
                className="note-menu-item"
                onClick={() => { close(); onPin?.(); }}
              >
                <IconPin size={14} stroke={1.6} filled={isPinned} />
                <span>{isPinned ? 'Unpin' : 'Pin'}</span>
              </button>
              {onEdit && (
                <button
                  className="note-menu-item"
                  onClick={() => { close(); onEdit(); }}
                >
                  <IconEdit size={14} stroke={1.6} />
                  <span>Rename</span>
                </button>
              )}
              {onMoveToGroup && (
                <button
                  className="note-menu-item"
                  onClick={() => { close(); onMoveToGroup(); }}
                >
                  <IconFolder size={14} stroke={1.5} />
                  <span>Move to group…</span>
                </button>
              )}
              <div className="note-menu-divider" />
              <button
                className="note-menu-item"
                onClick={() => { close(); onTrash?.(); }}
              >
                <IconArchive size={14} stroke={1.6} />
                <span>Archive</span>
              </button>
            </>
          )}
          {isTrashed && (
            <>
              <button
                className="note-menu-item"
                onClick={() => { close(); onRestore?.(); }}
              >
                <IconRestore size={14} stroke={1.6} />
                <span>Restore</span>
              </button>
              <div className="note-menu-divider" />
              <button
                className="note-menu-item danger"
                onClick={() => { close(); onDeletePermanently?.(); }}
              >
                <IconTrash size={14} stroke={1.6} />
                <span>Delete permanently</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
