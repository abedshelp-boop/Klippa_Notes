import { describe, it, expect } from 'vitest';
import { cardId, frameId, connectorId, noteCardId } from '../ids.js';

describe('canvas ids', () => {
  it('cardId returns a string prefixed with "card_"', () => {
    expect(cardId()).toMatch(/^card_[A-Za-z0-9_-]+$/);
  });

  it('frameId returns a string prefixed with "frame_"', () => {
    expect(frameId()).toMatch(/^frame_[A-Za-z0-9_-]+$/);
  });

  it('connectorId returns a string prefixed with "conn_"', () => {
    expect(connectorId()).toMatch(/^conn_[A-Za-z0-9_-]+$/);
  });

  it('noteCardId returns a string prefixed with "ncard_"', () => {
    expect(noteCardId()).toMatch(/^ncard_[A-Za-z0-9_-]+$/);
  });

  it('successive ids are unique', () => {
    const ids = new Set();
    for (let i = 0; i < 1000; i += 1) ids.add(cardId());
    expect(ids.size).toBe(1000);
  });

  it('ids across types do not collide', () => {
    const all = new Set();
    for (let i = 0; i < 250; i += 1) {
      all.add(cardId());
      all.add(frameId());
      all.add(connectorId());
      all.add(noteCardId());
    }
    expect(all.size).toBe(1000);
  });
});
