import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import useOuterCanvas from '../hooks/useOuterCanvas';
import {
  toReactFlow,
  fromReactFlow,
  createFreeConnector,
  matchesFilter,
} from '../lib/canvas/outer.js';
import NoteCardOnCanvas from './cards/NoteCardOnCanvas.jsx';
import OuterFrame from './canvas/OuterFrame.jsx';

const nodeTypes = {
  'note-card': NoteCardOnCanvas,
  frame: OuterFrame,
};

/**
 * Inner content — lives inside ReactFlowProvider so the useNodesState /
 * useEdgesState hooks have a flow instance to attach to.
 */
function OuterCanvasInner({
  notes, groups, overlay, filter, onOpenNote, onCreateNote,
}) {
  const { state, loading, commit } = useOuterCanvas({ notes, groups, overlay });

  const noteById = useMemo(() => {
    const map = new Map();
    for (const n of notes) map.set(n.id, n);
    return map;
  }, [notes]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Re-seed when the persisted state changes (initial load + reconciliation).
  // Keyed by the set of ids so we don't blow away in-flight position edits
  // when the user is just dragging.
  const seedKeyRef = useRef('');
  useEffect(() => {
    if (!state) return;
    const seedKey = JSON.stringify({
      n: state.noteCards.map((c) => c.id),
      f: state.frames.map((f) => f.id),
      e: state.connectors.map((c) => c.id),
    });
    if (seedKey === seedKeyRef.current) return;
    seedKeyRef.current = seedKey;
    const graph = toReactFlow(state);
    setNodes(graph.nodes);
    setEdges(graph.edges);
  }, [state, setNodes, setEdges]);

  // Decorate nodes with live note data + filter visibility + onOpen handler.
  const decoratedNodes = useMemo(() => {
    return nodes.map((n) => {
      if (n.type !== 'note-card') return n;
      const noteId = n.data?.noteId;
      const note = noteById.get(noteId);
      const cardMeta = state?.noteCards.find((c) => c.id === n.id) || {
        pinned: !!n.data?.pinned,
        tags: n.data?.tags || [],
        archived: !!n.data?.archived,
        frameId: n.parentId ?? null,
      };
      const visible = matchesFilter(cardMeta, filter);
      return {
        ...n,
        hidden: !visible,
        className: visible ? '' : 'oc-node-hidden',
        data: {
          ...n.data,
          note,
          pinned: cardMeta.pinned,
          tags: cardMeta.tags,
          archived: cardMeta.archived,
          onOpen: onOpenNote,
        },
      };
    });
  }, [nodes, noteById, state, filter, onOpenNote]);

  const onConnect = useCallback((params) => {
    if (!params?.source || !params?.target) return;
    const conn = createFreeConnector({
      sourceCardId: params.source, targetCardId: params.target,
    });
    setEdges((eds) => addEdge({
      id: conn.id,
      source: params.source,
      target: params.target,
      type: 'free',
      data: { kind: 'free' },
    }, eds));
  }, [setEdges]);

  // Debounced persistence — fire 400ms after the last change so we don't PUT
  // on every mouse-move tick during a drag.
  const commitTimerRef = useRef(null);
  useEffect(() => {
    if (!state) return;
    if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    commitTimerRef.current = setTimeout(() => {
      const graph = { nodes, edges };
      const next = fromReactFlow(graph,
        state.viewport || { x: 0, y: 0, zoom: 1 });
      commit(next);
    }, 400);
    return () => {
      if (commitTimerRef.current) clearTimeout(commitTimerRef.current);
    };
  }, [nodes, edges, state, commit]);

  const showEmpty = !loading && state && state.noteCards.length === 0;

  return (
    <div className="oc-root">
      {showEmpty && (
        <div className="oc-empty">
          <div className="oc-empty-headline">Nothing here yet.</div>
          <div className="oc-empty-hint">
            Say <span className="kbd">"Hey Deen"</span>
            {onCreateNote && (
              <>
                {' '}or{' '}
                <button
                  type="button"
                  className="oc-empty-cta"
                  onClick={onCreateNote}
                >
                  + Write a new note
                </button>
              </>
            )}
          </div>
        </div>
      )}
      <ReactFlow
        nodes={decoratedNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView={state ? state.noteCards.length > 0 : false}
        defaultViewport={state?.viewport || { x: 0, y: 0, zoom: 1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={24} />
        <Controls />
        <MiniMap zoomable pannable />
      </ReactFlow>
    </div>
  );
}

export default function OuterCanvas(props) {
  return (
    <ReactFlowProvider>
      <OuterCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
