import { describe, it, expect } from 'vitest';
import {
  isInnerCanvasState,
  isOuterCanvasState,
  emptyInnerCanvasState,
  emptyOuterCanvasState,
} from '../validators.js';

describe('canvas validators', () => {
  it('emptyInnerCanvasState round-trips through isInnerCanvasState', () => {
    expect(isInnerCanvasState(emptyInnerCanvasState())).toBe(true);
  });

  it('emptyOuterCanvasState round-trips through isOuterCanvasState', () => {
    expect(isOuterCanvasState(emptyOuterCanvasState())).toBe(true);
  });

  it('rejects null', () => {
    expect(isInnerCanvasState(null)).toBe(false);
    expect(isOuterCanvasState(null)).toBe(false);
  });

  it('rejects wrong schemaVersion', () => {
    const bad = { ...emptyInnerCanvasState(), schemaVersion: 99 };
    expect(isInnerCanvasState(bad)).toBe(false);
  });

  it('rejects missing arrays', () => {
    const bad = { schemaVersion: 1, cards: null, frames: [], connectors: [],
                  viewport: { x: 0, y: 0, zoom: 1 } };
    expect(isInnerCanvasState(bad)).toBe(false);
  });

  it('accepts a populated inner state', () => {
    const good = {
      schemaVersion: 1,
      cards: [{ id: 'card_x', type: 'text', position: { x: 0, y: 0 },
                size: { w: 100, h: 50 }, rotation: 0, frameId: null,
                data: { markdown: 'hi' } }],
      frames: [],
      connectors: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
    expect(isInnerCanvasState(good)).toBe(true);
  });
});
