import { describe, it, expect } from 'vitest';
import { migrateInnerCanvasState, CURRENT_SCHEMA_VERSION } from '../migrate.js';
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
