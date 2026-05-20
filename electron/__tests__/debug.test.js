import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createDebug } from '../debug.js';

describe('createDebug (electron main)', () => {
  let logSpy, warnSpy, errorSpy;

  beforeEach(() => {
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('log() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.log('Python', 'starting');
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('log() prints prefixed when isDev=true', () => {
    const d = createDebug(true);
    d.log('Python', 'starting', { port: 8765 });
    expect(logSpy).toHaveBeenCalledWith('[Python] starting', { port: 8765 });
  });

  it('warn() prints prefixed when isDev=true', () => {
    const d = createDebug(true);
    d.warn('Target', 'retry');
    expect(warnSpy).toHaveBeenCalledWith('[Target] retry');
  });

  it('warn() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.warn('Target', 'retry');
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('error() always prints, even when isDev=false', () => {
    const d = createDebug(false);
    d.error('Picker', 'list-notes failed', { err: 'ECONNREFUSED' });
    expect(errorSpy).toHaveBeenCalledWith('[Picker] list-notes failed', { err: 'ECONNREFUSED' });
  });
});
