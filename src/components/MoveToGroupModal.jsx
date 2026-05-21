import React, { useEffect, useMemo, useState } from 'react';
import { IconFolder, IconFolderOpen, IconChevronRight, IconChevronDown, IconX } from './Icons';

/**
 * MoveToGroupModal (Phase 9).
 *
 * Centered modal showing the group tree as selectable rows, plus an
 * "Ungrouped (root)" option at the top. Click a row → move the note via
 * the provided onMove handler and close.
 *
 * Also exposes "+ New group" to create a top-level group inline without
 * leaving the modal.
 */
export default function MoveToGroupModal({
  noteTitle,
  currentGroupId,
  groups,
  onMove,
  onCreateGroup,
  onClose,
}) {
  const tree = useMemo(() => buildTree(groups), [groups]);
  const [creating, setCreating] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSelect = async (groupId) => {
    await onMove?.(groupId);
    onClose?.();
  };

  const handleCreate = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    const created = await onCreateGroup?.(name, null);
    setCreating(false);
    setNewGroupName('');
    if (created?.id) await handleSelect(created.id);
  };

  return (
    <div className="modal-backdrop" onClick={(e) => {
      if (e.target === e.currentTarget) onClose?.();
    }}>
      <div className="modal move-modal" role="dialog" aria-modal="true">
        <div className="modal-header">
          <div className="modal-title">
            Move to group
            {noteTitle && <span className="modal-subtitle"> · {noteTitle}</span>}
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            <IconX size={14} stroke={1.6} />
          </button>
        </div>

        <div className="move-modal-body">
          <button
            type="button"
            className={`move-row root ${currentGroupId == null ? 'active' : ''}`}
            onClick={() => handleSelect(null)}
          >
            <span className="move-row-icon"><IconFolder size={13} stroke={1.5} /></span>
            <span className="move-row-label">Ungrouped (root)</span>
          </button>

          {tree.length > 0 && <div className="move-modal-divider" />}

          {tree.map((node) => (
            <MoveTreeNode
              key={node.id}
              node={node}
              depth={0}
              currentGroupId={currentGroupId}
              onSelect={handleSelect}
            />
          ))}

          {creating ? (
            <div className="move-create-row">
              <input
                autoFocus
                className="move-create-input"
                placeholder="Group name"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); handleCreate(); }
                  if (e.key === 'Escape') { e.preventDefault(); setCreating(false); }
                }}
              />
              <button
                type="button"
                className="move-create-btn"
                onClick={handleCreate}
                disabled={!newGroupName.trim()}
              >
                Create
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="move-create-trigger"
              onClick={() => setCreating(true)}
            >
              + New group
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function MoveTreeNode({ node, depth, currentGroupId, onSelect }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children.length > 0;
  const isActive = currentGroupId === node.id;

  return (
    <>
      <div
        className={`move-row ${isActive ? 'active' : ''}`}
        style={{ paddingLeft: 10 + depth * 14 }}
      >
        <button
          type="button"
          className="move-row-chevron"
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
          disabled={!hasChildren}
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {hasChildren ? (
            expanded ? <IconChevronDown size={11} /> : <IconChevronRight size={11} />
          ) : (
            <span className="move-row-chevron-spacer" />
          )}
        </button>
        <button
          type="button"
          className="move-row-main"
          onClick={() => onSelect(node.id)}
        >
          <span className="move-row-icon">
            {expanded && hasChildren
              ? <IconFolderOpen size={13} stroke={1.5} />
              : <IconFolder size={13} stroke={1.5} />}
          </span>
          <span className="move-row-label">{node.name}</span>
        </button>
      </div>
      {expanded && hasChildren && node.children.map((c) => (
        <MoveTreeNode
          key={c.id}
          node={c}
          depth={depth + 1}
          currentGroupId={currentGroupId}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

function buildTree(groups) {
  const byParent = new Map();
  for (const g of groups) {
    const key = g.parent_id || '__root__';
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(g);
  }
  const sortNodes = (arr) =>
    arr.sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    );
  function buildChildren(parentKey) {
    const arr = byParent.get(parentKey) || [];
    sortNodes(arr);
    return arr.map((g) => ({ ...g, children: buildChildren(g.id) }));
  }
  return buildChildren('__root__');
}
