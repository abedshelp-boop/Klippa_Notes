import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { debug } from '../lib/debug';

// Initialize once at module scope (not in a component effect — StrictMode
// would otherwise double-initialize). v11 default securityLevel='strict'
// blocks click handlers / HTML labels in node text, which is what we want.
let _mermaidReady = false;
function ensureMermaidInit() {
  if (_mermaidReady) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'strict',
    fontFamily:
      'ui-serif, Georgia, Cambria, "Times New Roman", Times, serif',
  });
  _mermaidReady = true;
}

let _seq = 0;

/**
 * Render a fenced ```mermaid block as an SVG. Uses mermaid.render() (pure;
 * returns {svg} as a string) instead of mermaid.run() (DOM-mutating;
 * misbehaves under React StrictMode's double-mount).
 */
export default function MermaidBlock({ code }) {
  const ref = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    ensureMermaidInit();
    let cancelled = false;
    const id = `mermaid-${++_seq}-${Math.floor(Math.random() * 1e6)}`;
    setError(null);

    (async () => {
      try {
        const { svg } = await mermaid.render(id, code);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
        }
      } catch (err) {
        if (!cancelled) {
          debug.error('Mermaid', 'render failed', err);
          setError(err?.message || String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <div className="mermaid-error">
        <div className="mermaid-error-label">Mermaid diagram error</div>
        <pre className="mermaid-error-detail">{error}</pre>
        <pre className="mermaid-error-source">{code}</pre>
      </div>
    );
  }

  return <div ref={ref} className="mermaid-block" />;
}
