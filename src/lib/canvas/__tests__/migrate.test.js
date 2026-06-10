// @ts-nocheck
// Tests read Card.data.markdown directly; the runtime always returns
// TextCardData here, but the JSDoc discriminated union can't be narrowed
// from .type at the test-call site without verbose assertions.
import { describe, it, expect } from 'vitest';
import {
  migrateInnerCanvasState,
  migrateLegacyMarkdown,
  CURRENT_SCHEMA_VERSION,
} from '../migrate.js';
import { emptyInnerCanvasState, isInnerCanvasState } from '../validators.js';

describe('canvas migrate', () => {
  it('CURRENT_SCHEMA_VERSION is 1', () => {
    expect(CURRENT_SCHEMA_VERSION).toBe(1);
  });

  it('null input migrates to empty inner state', () => {
    const result = migrateInnerCanvasState(null);
    expect(isInnerCanvasState(result)).toBe(true);
    expect(result.cards).toEqual([]);
  });

  it('a valid current-version state passes through unchanged', () => {
    const state = emptyInnerCanvasState();
    const result = migrateInnerCanvasState(state);
    expect(result).toEqual(state);
  });

  it('invalid input migrates to empty state', () => {
    const result = migrateInnerCanvasState({ junk: true });
    expect(isInnerCanvasState(result)).toBe(true);
    expect(result.cards).toEqual([]);
  });
});

describe('migrateLegacyMarkdown', () => {
  it('returns valid InnerCanvasState with one text card holding the content', () => {
    const state = migrateLegacyMarkdown('# hello\n\nworld');
    expect(isInnerCanvasState(state)).toBe(true);
    expect(state.cards).toHaveLength(1);
    expect(state.cards[0].type).toBe('text');
    expect(state.cards[0].data.markdown).toBe('# hello\n\nworld');
  });

  it('handles empty string', () => {
    const state = migrateLegacyMarkdown('');
    expect(isInnerCanvasState(state)).toBe(true);
    expect(state.cards[0].data.markdown).toBe('');
  });

  it('handles null', () => {
    const state = migrateLegacyMarkdown(null);
    expect(isInnerCanvasState(state)).toBe(true);
    expect(state.cards[0].data.markdown).toBe('');
  });

  it('handles undefined', () => {
    const state = migrateLegacyMarkdown(undefined);
    expect(isInnerCanvasState(state)).toBe(true);
    expect(state.cards[0].data.markdown).toBe('');
  });

  it('is idempotent through migrateInnerCanvasState', () => {
    const first = migrateLegacyMarkdown('content text');
    const second = migrateInnerCanvasState(first);
    expect(second).toEqual(first);
  });

  it('positions the card at (0,0) as required by the spec', () => {
    const state = migrateLegacyMarkdown('x');
    expect(state.cards[0].position).toEqual({ x: 0, y: 0 });
  });
});
