import { describe, it, expect } from 'vitest';

describe('canary', () => {
  it('proves the Vitest runner is wired correctly', () => {
    expect(1 + 1).toBe(2);
  });
});
