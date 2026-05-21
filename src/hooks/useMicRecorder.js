import { useCallback, useEffect, useRef, useState } from 'react';
import { debug } from '../lib/debug';

/**
 * Mic recorder hook (Phase 7).
 *
 * Captures the user's microphone via getUserMedia + AudioContext, accumulates
 * raw PCM samples, and on stop() returns a 16-bit mono WAV Blob ready to POST
 * to /transcribe-push-to-talk.
 *
 * Why WAV (and not MediaRecorder's webm/opus default): the Python service
 * decodes via soundfile + OpenAI Whisper. WAV avoids needing ffmpeg in Python.
 *
 * Note: this uses ScriptProcessorNode (deprecated but still supported across
 * all Chromium versions Electron ships with). AudioWorklet is the modern
 * replacement but requires a separate worklet module file — overkill for
 * short dictation captures.
 */
export default function useMicRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState(null);

  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const chunksRef = useRef([]);
  const sampleRateRef = useRef(0);

  const cleanup = useCallback(() => {
    if (processorRef.current) {
      try {
        processorRef.current.disconnect();
        processorRef.current.onaudioprocess = null;
      } catch {}
      processorRef.current = null;
    }
    if (sourceRef.current) {
      try { sourceRef.current.disconnect(); } catch {}
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch {}
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((t) => t.stop());
      } catch {}
      streamRef.current = null;
    }
  }, []);

  // Defensive: unmount mid-recording shouldn't leave a hot mic running.
  useEffect(() => () => cleanup(), [cleanup]);

  const start = useCallback(async () => {
    if (isRecording) return false;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      audioContextRef.current = ctx;
      sampleRateRef.current = ctx.sampleRate;

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // 4096-sample buffer = ~85ms at 48kHz. Low enough latency that stop()
      // captures the user's full intent; high enough to keep CPU sane.
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      chunksRef.current = [];

      processor.onaudioprocess = (event) => {
        // Copy — input buffer is reused across callbacks.
        const channel = event.inputBuffer.getChannelData(0);
        chunksRef.current.push(new Float32Array(channel));
      };

      source.connect(processor);
      // Necessary in older Chromium: a ScriptProcessor must be connected
      // to a destination to actually run, even if it produces no output.
      processor.connect(ctx.destination);

      setIsRecording(true);
      return true;
    } catch (err) {
      debug.error('Mic', 'start failed', err);
      setError(err?.message || 'Microphone access denied');
      cleanup();
      return false;
    }
  }, [isRecording, cleanup]);

  /**
   * Stops recording and returns a 16-bit mono WAV Blob. Returns null if
   * nothing was captured (no audio samples or recorder wasn't started).
   */
  const stop = useCallback(async () => {
    if (!isRecording) return null;
    setIsRecording(false);

    const chunks = chunksRef.current;
    const sampleRate = sampleRateRef.current;
    chunksRef.current = [];

    cleanup();

    const totalLength = chunks.reduce((s, c) => s + c.length, 0);
    if (totalLength === 0 || sampleRate === 0) return null;

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    return encodeWav(merged, sampleRate);
  }, [isRecording, cleanup]);

  return { start, stop, isRecording, error };
}

/**
 * Encode Float32 PCM samples into a 16-bit mono WAV Blob.
 * Spec ref: http://soundfile.sapp.org/doc/WaveFormat/
 */
function encodeWav(samples, sampleRate) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const dataSize = samples.length * 2; // int16 = 2 bytes
  const bufferSize = 44 + dataSize;

  const buffer = new ArrayBuffer(bufferSize);
  const view = new DataView(buffer);
  let p = 0;
  const writeString = (s) => { for (let i = 0; i < s.length; i++) view.setUint8(p++, s.charCodeAt(i)); };
  const writeUint32 = (v) => { view.setUint32(p, v, true); p += 4; };
  const writeUint16 = (v) => { view.setUint16(p, v, true); p += 2; };

  writeString('RIFF');
  writeUint32(bufferSize - 8);
  writeString('WAVE');
  writeString('fmt ');
  writeUint32(16);             // PCM fmt chunk size
  writeUint16(1);              // PCM format
  writeUint16(numChannels);
  writeUint32(sampleRate);
  writeUint32(byteRate);
  writeUint16(blockAlign);
  writeUint16(bitsPerSample);
  writeString('data');
  writeUint32(dataSize);

  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(p, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    p += 2;
  }

  return new Blob([buffer], { type: 'audio/wav' });
}
