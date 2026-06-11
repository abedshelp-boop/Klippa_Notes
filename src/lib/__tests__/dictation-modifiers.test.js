import { describe, it, expect } from 'vitest';
import {
  DICTATION_MODE,
  HOTKEY_LABEL,
  pickDictationMode,
  parseVoicePrefix,
} from '../dictation-modifiers';

describe('DICTATION_MODE', () => {
  it('exposes both modes', () => {
    expect(DICTATION_MODE.REWRITE).toBe('rewrite');
    expect(DICTATION_MODE.VERBATIM).toBe('verbatim');
  });
});

describe('pickDictationMode', () => {
  const ev = (overrides) => ({
    code: 'Space',
    ctrlKey: true,
    metaKey: false,
    shiftKey: false,
    altKey: false,
    ...overrides,
  });

  it('returns rewrite for Ctrl+Space', () => {
    expect(pickDictationMode(ev())).toBe(DICTATION_MODE.REWRITE);
  });

  it('returns rewrite for Cmd+Space (mac)', () => {
    expect(pickDictationMode(ev({ ctrlKey: false, metaKey: true }))).toBe(
      DICTATION_MODE.REWRITE,
    );
  });

  it('returns verbatim for Shift+Ctrl+Space', () => {
    expect(pickDictationMode(ev({ shiftKey: true }))).toBe(
      DICTATION_MODE.VERBATIM,
    );
  });

  it('returns null for non-Space keys', () => {
    expect(pickDictationMode(ev({ code: 'Enter' }))).toBeNull();
  });

  it('returns null when no ctrl/meta modifier is held', () => {
    expect(pickDictationMode(ev({ ctrlKey: false }))).toBeNull();
  });

  it('returns null when Alt is involved (avoid clobbering window shortcuts)', () => {
    expect(pickDictationMode(ev({ altKey: true }))).toBeNull();
  });
});

describe('parseVoicePrefix', () => {
  it('strips "quote:" prefix and flips to verbatim', () => {
    expect(parseVoicePrefix('quote: hello world')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'hello world',
    });
  });

  it('strips "verbatim:" prefix and flips to verbatim', () => {
    expect(parseVoicePrefix('verbatim: hi')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'hi',
    });
  });

  it('is case-insensitive on the prefix', () => {
    expect(parseVoicePrefix('Quote: hi')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'hi',
    });
    expect(parseVoicePrefix('VERBATIM: hi')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'hi',
    });
  });

  it('tolerates missing space after the colon', () => {
    expect(parseVoicePrefix('quote:hello')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'hello',
    });
  });

  it('leaves text alone when no prefix is present', () => {
    expect(parseVoicePrefix('regular text')).toEqual({
      mode: DICTATION_MODE.REWRITE,
      text: 'regular text',
    });
  });

  it('handles leading whitespace before the prefix', () => {
    expect(parseVoicePrefix('   quote: trimmed')).toEqual({
      mode: DICTATION_MODE.VERBATIM,
      text: 'trimmed',
    });
  });

  it('returns rewrite mode + empty text on empty input', () => {
    expect(parseVoicePrefix('')).toEqual({
      mode: DICTATION_MODE.REWRITE,
      text: '',
    });
  });
});

describe('HOTKEY_LABEL', () => {
  it('exposes display strings for both modes', () => {
    expect(HOTKEY_LABEL.REWRITE).toMatch(/Ctrl\+Space/);
    expect(HOTKEY_LABEL.VERBATIM).toMatch(/Shift\+Ctrl\+Space/);
  });
});
