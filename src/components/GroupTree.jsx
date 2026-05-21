import React, { useMemo, useState } from 'react';
import {
  IconChevronRight,
  IconChevronDown,
  IconFolder,
  IconFolderOpen,
  IconPlus,
  IconEdit,
  IconTrash,
} from './Icons';

/**
 * GroupTree (Phase 9).
 *
 * Renders the nested group hierarchy as a collapsible tree in the sidebar.
 * Builds the tree client-side from a flat list of {id, name, parent_id}.
 *
 * Click a row → select that group as the active filter.
 * Click chevron → expand/collapse children.
 * Double-click name → rename inline.
 * Hover row → reveal action buttons (new subgroup, rename, delete).
 *
 * The tree is recursive but capped at a sane depth visually via padding.
 */
export default function GroupTree({
  groups,
  notes,
  activeGroupId,
  onSelectGroup,
  onCreateGroup,
  onRenameGroup,
  onDeleteGroup,
}) {
  const tree = useMemo(() => buildTree(groups), [groups]);
  const countsByGroup = useMemo(() => buildCounts(groups, notes), [groups, notes]);

  return (
    <div className="group-tree">
      {tree.map((node) => (
        <GroupNode
          key={node.id}
          node={node}
          depth={0}
          activeGroupId={activeGroupId}
          counts={countsByGroup}
          onSelectGroup={onSelectGroup}
          onCreateGroup={onCreateGroup}
          onRenameGroup={onRenameGroup}
          onDeleteGroup={onDeleteGroup}
        />
      ))}
      {tree.length === 0 && (
        <div className="group-tree-empty">No groups yet.</div>
      )}
    </div>
  );
}

function buildTree(groups) {
  const byParent = new Map();
  for (const g of groups) {
    const key = g.parent_id || '__root__';
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(g);
  }
  // Detach cycles: if a parent_id points at a non-existent group, treat as root.
  const validIds = new Set(groups.map((g) => g.id));
  for (const g of groups) {
    if (g.parent_id && !validIds.has(g.parent_id)) {
      const arr = byParent.get('__root__') || [];
      arr.push(g);
      byParent.set('__root__', arr);
      // remove from the bogus parent's slot
      const wrong = byParent.get(g.parent_id);
      if (wrong) {
        const idx = wrong.findIndex((x) => x.id === g.id);
        if (idx >= 0) wrong.splice(idx, 1);
      }
    }
  }

  const sortNodes = (arr) =>
    arr.sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    );

  function buildChildren(parentKey) {
    const arr = byParent.get(parentKey) || [];
    sortNodes(arr);
    return arr.map((g) => ({
      ...g,
      children: buildChildren(g.id),
    }));
  }
  return buildChildren('__root__');
}

function buildCounts(groups, notes) {
  // Direct count per group_id.
  const direct = new Map();
  for (const n of notes) {
    if (!n.group_id) continue;
    direct.set(n.group_id, (direct.get(n.group_id) || 0) + 1);
  }
  // Recursive count (own + descendants).
  const childrenOf = new Map();
  for (const g of groups) {
    const key = g.parent_id || '__root__';
    if (!childrenOf.has(key)) childrenOf.set(key, []);
    childrenOf.get(key).push(g.id);
  }
  const recursive = new Map();
  function compute(id) {
    if (recursive.has(id)) return recursive.get(id);
    let total = direct.get(id) || 0;
    for (const childId of childrenOf.get(id) || []) {
      total += compute(childId);
    }
    recursive.set(id, total);
    return total;
  }
  for (const g of groups) compute(g.id);
  return recursive;
}

function GroupNode({
  node,
  depth,
  activeGroupId,
  counts,
  onSelectGroup,
  onCreateGroup,
  onRenameGroup,
  onDeleteGroup,
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(node.name);

  const isActive = activeGroupId === node.id;
  const hasChildren = node.children.length > 0;
  const count = counts.get(node.id) || 0;

  const startRename = () => {
    setDraft(node.name);
    setEditing(true);
  };

  const commitRename = () => {
    const trimmed = draft.trim();
    setEditing(false);
    if (!trimmed || trimmed === node.name) return;
    onRenameGroup?.(node.id, trimmed);
  };

  const addSubgroup = async () => {
    const name = window.prompt(`New subgroup under "${node.name}"`, '');
    if (!name || !name.trim()) return;
    setExpanded(true);
    await onCreateGroup?.(name.trim(), node.id);
  };

  const confirmDelete = async () => {
    const ok = window.confirm(
      `Delete group "${node.name}"?\n\nNotes inside will become ungrouped. ` +
      `Subgroups will move to the top level. This cannot be undone.`,
    );
    if (!ok) return;
    await onDeleteGroup?.(node.id);
  };

  return (
    <div className="group-tree-node">
      <div
        className={`group-tree-row ${isActive ? 'active' : ''}`}
        style={{ paddingLeft: 8 + depth * 14 }}
      >
        <button
          type="button"
          className="group-tree-chevron"
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
          aria-label={expanded ? 'Collapse' : 'Expand'}
          disabled={!hasChildren}
          title={hasChildren ? (expanded ? 'Collapse' : 'Expand') : ''}
        >
          {hasChildren ? (
            expanded
              ? <IconChevronDown size={11} stroke={1.8} />
              : <IconChevronRight size={11} stroke={1.8} />
          ) : (
            <span className="group-tree-chevron-spacer" />
          )}
        </button>

        <span className="group-tree-icon">
          {expanded && hasChildren
            ? <IconFolderOpen size={13} stroke={1.5} />
            : <IconFolder size={13} stroke={1.5} />}
        </span>

        {editing ? (
          <input
            autoFocus
            className="group-tree-rename-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
              if (e.key === 'Escape') { e.preventDefault(); setEditing(false); }
            }}
            maxLength={80}
          />
        ) : (
          <button
            type="button"
            className="group-tree-label"
            onClick={() => onSelectGroup?.(node.id)}
            onDoubleClick={startRename}
            title="Click to filter · double-click to rename"
          >
            {node.name}
          </button>
        )}

        <span className="group-tree-count">{count || ''}</span>

        <div className="group-tree-actions">
          <button
            type="button"
            className="group-tree-action"
            onClick={addSubgroup}
            title="New subgroup"
            aria-label="New subgroup"
          >
            <IconPlus size={10} stroke={1.8} />
          </button>
          <button
            type="button"
            className="group-tree-action"
            onClick={startRename}
            title="Rename"
            aria-label="Rename group"
          >
            <IconEdit size={10} stroke={1.6} />
          </button>
          <button
            type="button"
            className="group-tree-action danger"
            onClick={confirmDelete}
            title="Delete group"
            aria-label="Delete group"
          >
            <IconTrash size={10} stroke={1.6} />
          </button>
        </div>
      </div>

      {expanded && hasChildren && (
        <div className="group-tree-children">
          {node.children.map((child) => (
            <GroupNode
              key={child.id}
              node={child}
              depth={depth + 1}
              activeGroupId={activeGroupId}
              counts={counts}
              onSelectGroup={onSelectGroup}
              onCreateGroup={onCreateGroup}
              onRenameGroup={onRenameGroup}
              onDeleteGroup={onDeleteGroup}
            />
          ))}
        </div>
      )}
    </div>
  );
}
