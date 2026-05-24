import React from 'react';

/**
 * Minimal outer-canvas frame node. Renders a labeled translucent backdrop.
 * Child note-card nodes are positioned by React Flow above this backdrop
 * via `parentId` + `extent: 'parent'`.
 *
 * Sub-project 2 may unify this with an inner-canvas Frame component later;
 * keeping it minimal until then.
 *
 * Expected `data` shape: { label: string, isAutoLooseIdeas?: boolean }
 */
export default function OuterFrame({ data }) {
  const label = (data?.label || '').trim() || 'Untitled Frame';
  const cls = [
    'oc-frame',
    data?.isAutoLooseIdeas ? 'is-loose' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <div className="oc-frame-label">{label}</div>
    </div>
  );
}
