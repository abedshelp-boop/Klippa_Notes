import React from 'react';
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import TextCard from '../TextCard.jsx';

// React Flow's <Handle> calls hooks that require ReactFlowProvider context.
// We bypass that for render-shape tests with the isPreview prop, which
// skips Handle wiring entirely. In production, isPreview is always
// falsy — InnerCanvas wraps TextCard in a <ReactFlowProvider>.

describe('TextCard', () => {
  it('renders the markdown body in display mode', () => {
    const html = renderToStaticMarkup(
      <TextCard
        id="card_test"
        data={{ markdown: '# Hello\n\nWorld' }}
        isPreview
      />,
    );
    expect(html).toContain('<h1');
    expect(html).toContain('Hello');
    expect(html).toContain('World');
  });

  it('renders an empty card without crashing when markdown is empty', () => {
    const html = renderToStaticMarkup(
      <TextCard id="card_test" data={{ markdown: '' }} isPreview />,
    );
    expect(html).toContain('ic-textcard');
  });

  it('applies the ic-textcard CSS namespace', () => {
    const html = renderToStaticMarkup(
      <TextCard id="card_test" data={{ markdown: 'x' }} isPreview />,
    );
    expect(html).toMatch(/class="[^"]*ic-textcard/);
  });

  it('renders fenced code blocks as <code>', () => {
    const html = renderToStaticMarkup(
      <TextCard
        id="card_test"
        data={{ markdown: '```js\nconst x = 1;\n```' }}
        isPreview
      />,
    );
    expect(html).toContain('<code');
    expect(html).toContain('language-js');
    // rehype-highlight wraps tokens in <span>, so the full string is split.
    // Assert on individual fragments instead.
    expect(html).toContain('const');
    expect(html).toContain('1');
  });

  it('omits Handle elements in isPreview mode', () => {
    const html = renderToStaticMarkup(
      <TextCard id="card_test" data={{ markdown: 'x' }} isPreview />,
    );
    // React Flow's Handle component renders a div with class react-flow__handle.
    expect(html).not.toContain('react-flow__handle');
  });
});
