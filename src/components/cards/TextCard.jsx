import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { Handle, Position } from '@xyflow/react';
import MermaidBlock from '../MermaidBlock';
import ChartBlock from '../ChartBlock';

/**
 * Sanitize schema copied verbatim from NoteView.jsx — allows inline SVG
 * (so the AI can hand-author small diagrams) while blocking <script>,
 * <foreignObject>, on* handlers via the default allow-list.
 *
 * Mermaid + chart fenced blocks bypass this entirely; their custom
 * components.code override receives raw fenced text.
 */
const SVG_TAGS = [
  'svg', 'g', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon',
  'text', 'tspan', 'defs', 'clipPath', 'mask', 'linearGradient', 'stop',
  'title', 'desc', 'use', 'symbol',
];
const SVG_ATTRS = [
  'viewBox', 'xmlns', 'd', 'fill', 'stroke', 'strokeWidth', 'strokeLinecap',
  'strokeLinejoin', 'strokeDasharray', 'transform', 'cx', 'cy', 'r',
  'x', 'y', 'x1', 'y1', 'x2', 'y2', 'points', 'width', 'height',
  'opacity', 'fillOpacity', 'strokeOpacity', 'fontSize', 'textAnchor',
  'fontFamily', 'fontWeight',
  'offset', 'stopColor', 'stopOpacity', 'gradientUnits',
  'gradientTransform', 'clipPathUnits', 'href', 'preserveAspectRatio',
];

const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), ...SVG_TAGS],
  attributes: {
    ...defaultSchema.attributes,
    '*': [
      ...(defaultSchema.attributes?.['*'] || []),
      ...SVG_ATTRS,
    ],
  },
};

const REMARK_PLUGINS = [remarkGfm, remarkMath];
/* Plugin order is load-bearing — same rationale as NoteView.jsx:
   1. rehypeRaw — re-parse raw HTML so inline <svg> becomes real hast nodes.
   2. rehypeKatex / rehypeHighlight — transform math + code into span trees.
   3. rehypeSanitize LAST — strip everything not in the allow-list. */
const REHYPE_PLUGINS = [
  rehypeRaw,
  rehypeKatex,
  rehypeHighlight,
  [rehypeSanitize, SANITIZE_SCHEMA],
];

const MARKDOWN_COMPONENTS = {
  code({ className, children, ...props }) {
    const text = String(children || '').replace(/\n$/, '');
    if (className === 'language-mermaid') return <MermaidBlock code={text} />;
    if (className === 'language-chart') return <ChartBlock source={text} />;
    return <code className={className} {...props}>{children}</code>;
  },
};

/**
 * A single text card on the inner canvas.
 *
 * Display mode: renders `data.markdown` through the existing react-markdown
 * pipeline (mermaid + chart + KaTeX preserved exactly).
 *
 * Edit mode: replaces the rendered body with a textarea bound to a local
 * draft. Enter edit by double-clicking the body (matches NoteView's
 * "double-click to rename" pattern). Commit on blur or Ctrl+Enter; cancel
 * on Escape. Commit calls the `onCommitMarkdown` prop with the new value.
 *
 * The `isPreview` prop short-circuits React Flow's <Handle> wiring so the
 * component can be rendered outside a ReactFlowProvider (used by tests
 * and by any future "thumbnail" rendering). In production, isPreview is
 * always falsy — the surrounding <ReactFlow> provides the required context.
 *
 * @param {{
 *   id: string,
 *   data: { markdown: string, onCommitMarkdown?: function, onEditingChange?: function },
 *   onCommitMarkdown?: (cardId: string, markdown: string) => void,
 *   onEditingChange?: (cardId: string, editing: boolean) => void,
 *   isPreview?: boolean,
 * }} props
 *
 * React Flow passes the node's `data` object verbatim to the custom node.
 * InnerCanvas injects `onCommitMarkdown` and `onEditingChange` into `data`
 * so the callback identity stays stable per parent render. We support
 * both `props.onCommitMarkdown` (used by tests) and `data.onCommitMarkdown`
 * (used by React Flow's runtime).
 */
export default function TextCard({
  id,
  data,
  onCommitMarkdown: directOnCommitMarkdown,
  onEditingChange: directOnEditingChange,
  isPreview = false,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const textareaRef = useRef(null);

  const onCommitMarkdown = directOnCommitMarkdown || data?.onCommitMarkdown;
  const onEditingChange = directOnEditingChange || data?.onEditingChange;

  // Notify parent (InnerCanvas) so it can flip React Flow's draggable off
  // while editing — otherwise text selection inside the textarea would
  // start a drag and the user couldn't select text.
  useEffect(() => {
    if (onEditingChange) onEditingChange(id, editing);
  }, [editing, id, onEditingChange]);

  const beginEdit = useCallback(() => {
    setDraft(data?.markdown ?? '');
    setEditing(true);
    setTimeout(() => {
      const el = textareaRef.current;
      if (el) {
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
        el.focus();
      }
    }, 10);
  }, [data?.markdown]);

  const commit = useCallback(() => {
    setEditing(false);
    const next = draft;
    if (next === (data?.markdown ?? '')) return;
    if (onCommitMarkdown) onCommitMarkdown(id, next);
  }, [draft, data?.markdown, id, onCommitMarkdown]);

  const cancel = useCallback(() => {
    setEditing(false);
    setDraft('');
  }, []);

  const handleChange = useCallback((e) => {
    setDraft(e.target.value);
    // Auto-resize the textarea like NoteView did.
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  }, []);

  const handleKeyDown = useCallback((e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      commit();
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      cancel();
    }
  }, [commit, cancel]);

  const markdown = data?.markdown ?? '';

  return (
    <div className={`ic-textcard ${editing ? 'editing' : ''}`}>
      {!isPreview && (
        <>
          <Handle type="target" position={Position.Top} isConnectable={false} />
          <Handle type="source" position={Position.Bottom} isConnectable={false} />
        </>
      )}
      {editing ? (
        <textarea
          ref={textareaRef}
          className="ic-textcard-editor"
          value={draft}
          onChange={handleChange}
          onBlur={commit}
          onKeyDown={handleKeyDown}
          spellCheck
          placeholder="Start typing…"
          /* Stop drag / wheel / select propagation so React Flow's pan +
             zoom handlers don't intercept while editing. */
          onMouseDown={(e) => e.stopPropagation()}
          onWheel={(e) => e.stopPropagation()}
        />
      ) : (
        <div
          className="ic-textcard-body markdown-body"
          onDoubleClick={beginEdit}
          title="Double-click to edit"
        >
          <ReactMarkdown
            remarkPlugins={REMARK_PLUGINS}
            rehypePlugins={REHYPE_PLUGINS}
            components={MARKDOWN_COMPONENTS}
          >
            {markdown}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
