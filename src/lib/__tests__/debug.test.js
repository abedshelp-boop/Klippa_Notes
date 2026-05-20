import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createDebug } from '../debug.js';

describe('createDebug (renderer)', () => {
  let logSpy, warnSpy, errorSpy;

  beforeEach(() => {
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('log() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.log('Sub', 'message', { extra: 1 });
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('log() prints prefixed message when isDev=true', () => {
    const d = createDebug(true);
    d.log('Sub', 'message', { extra: 1 });
    expect(logSpy).toHaveBeenCalledWith('[Sub] message', { extra: 1 });
  });

  it('warn() is a no-op when isDev=false', () => {
    const d = createDebug(false);
    d.warn('Sub', 'careful');
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('warn() prints prefixed message when isDev=true', () => {
    const d = createDebug(true);
    d.warn('Sub', 'careful', 42);
    expect(warnSpy).toHaveBeenCalledWith('[Sub] careful', 42);
  });

  it('error() ALWAYS prints, even when isDev=false', () => {
    const d = createDebug(false);
    d.error('Sub', 'boom', { code: 500 });
    expect(errorSpy).toHaveBeenCalledWith('[Sub] boom', { code: 500 });
  });

  it('error() prints when isDev=true', () => {
    const d = createDebug(true);
    d.error('Sub', 'boom');
    expect(errorSpy).toHaveBeenCalledWith('[Sub] boom');
  });
});
