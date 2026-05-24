/**
 * Shared dictation helpers — imported by today's NoteView and tomorrow's
 * InnerCanvas/TextCard alike so the dictation surface lives in one place.
 *
 * Sub-project 4 collapses the two-mode picker. The user only sees a single
 * armed mic. AI Rewrite is the default; Verbatim survives as a modifier via:
 *   - Hotkey:        Shift+Ctrl+Space  (Ctrl+Space stays rewrite)
 *   - Voice prefix:  "quote:" / "verbatim:" at the start of the utterance
 */

import { debug } from './debug';

const API_URL = 'http://localhost:8765';

/** @typedef {'rewrite' | 'verbatim'} DictationMode */

/** @type {{ REWRITE: 'rewrite', VERBATIM: 'verbatim' }} */
export const DICTATION_MODE = Object.freeze({
  REWRITE: 'rewrite',
  VERBATIM: 'verbatim',
});

export const HOTKEY_LABEL = Object.freeze({
  REWRITE: 'Ctrl+Space',
  VERBATIM: 'Shift+Ctrl+Space',
});

/**
 * Decide which dictation mode (if any) the given key event represents.
 * Returns null for events that should not arm a dictation. Alt is excluded
 * so we don't clobber OS-level Alt+Space shortcuts.
 *
 * @param {Pick<KeyboardEvent, 'code' | 'ctrlKey' | 'metaKey' | 'shiftKey' | 'altKey'>} event
 * @returns {DictationMode | null}
 */
export function pickDictationMode(event) {
  if (!event) return null;
  if (event.code !== 'Space') return null;
  if (event.altKey) return null;
  if (!(event.ctrlKey || event.metaKey)) return null;
  return event.shiftKey ? DICTATION_MODE.VERBATIM : DICTATION_MODE.REWRITE;
}

const VOICE_PREFIX_RE = /^\s*(quote|verbatim)\s*:\s*/i;

/**
 * Strip a leading "quote:" / "verbatim:" marker from a transcript or
 * still-being-typed string and return both the residual text and the
 * resulting mode. With no marker, returns rewrite (the default).
 *
 * @param {string} input
 * @returns {{ mode: DictationMode, text: string }}
 */
export function parseVoicePrefix(input) {
  const raw = typeof input === 'string' ? input : '';
  const match = raw.match(VOICE_PREFIX_RE);
  if (match) {
    return {
      mode: DICTATION_MODE.VERBATIM,
      text: raw.slice(match[0].length),
    };
  }
  return { mode: DICTATION_MODE.REWRITE, text: raw };
}

/**
 * Fire-and-forget hear-back confirmation through Kokoro TTS. Never throws —
 * a missing service, network blip, or audio-policy block must not interrupt
 * the user-visible "saved" path. Returns true if playback was kicked off.
 *
 * Prefers the Electron IPC bridge (window.electronAPI.ttsSay) so the main
 * process can centralize fetch + caching. Falls back to a direct fetch when
 * running under vitest / browser preview where the bridge isn't installed.
 *
 * @param {string} noteTitle
 * @returns {Promise<boolean>}
 */
export async function sayConfirmation(noteTitle) {
  const title = (noteTitle || '').trim() || 'note';
  const text = `Saved to ${title}`;

  try {
    /** @type {ArrayBuffer | null} */
    let buffer = null;

    const bridge = typeof window !== 'undefined' ? window.electronAPI : null;
    if (bridge && typeof bridge.ttsSay === 'function') {
      buffer = await bridge.ttsSay(text);
    } else if (typeof fetch === 'function') {
      const res = await fetch(
        `${API_URL}/tts/say?text=${encodeURIComponent(text)}`,
      );
      if (!res.ok) return false;
      buffer = await res.arrayBuffer();
    }

    if (!buffer || buffer.byteLength === 0) return false;
    if (typeof Audio !== 'function' || typeof URL === 'undefined') return false;

    const blob = new Blob([buffer], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = 0.8;
    audio.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
    audio.addEventListener('error', () => URL.revokeObjectURL(url), { once: true });
    await audio.play();
    return true;
  } catch (err) {
    debug.warn('Dictation', 'hear-back failed (non-fatal)', err);
    return false;
  }
}
