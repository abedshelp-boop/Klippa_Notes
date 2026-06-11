# Sub-project 4: Dictation Collapse + Model Swaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two-mode dictation picker to AI-Rewrite-by-default with verbatim as a `Shift+Ctrl+Space` / `"quote:"` modifier; route push-to-talk and capture transcription through Deepgram Nova-3 with `faster-whisper` as offline fallback; add Kokoro TTS hear-back confirmations; lock sacred-content rules into the rewrite prompt.

**Architecture:**
1. Renderer: extract shared dictation logic into `src/lib/dictation-modifiers.js` so both today's `NoteView.jsx` and tomorrow's `InnerCanvas`/`TextCard` import the same helpers. The mode picker dies; a single armed mic is always there, with `Ctrl+Space`=rewrite, `Shift+Ctrl+Space`=verbatim. On capture success, fire-and-forget hear-back via Electron IPC → Python `/tts/say`.
2. Python service: layered transcription chain — Deepgram Nova-3 (primary) → `faster-whisper` (offline fallback) → existing OpenAI / AssemblyAI (legacy fallback while keys are present). New `tts_kokoro.py` lazy-loads kokoro-onnx and exposes a `/tts/say` HTTP endpoint that returns WAV bytes. The AI rewrite prompt gains a SACRED CONTENT block that enumerates always-verbatim spans (quoted strings, code-like identifiers, proper nouns, brand names, numbers+units, URLs).

**Tech Stack:**
- Renderer: React 19, Vitest 3
- Electron: ipcRenderer/ipcMain (existing pattern)
- Python service: FastAPI, `deepgram-sdk>=5.0.0`, `kokoro-onnx`, `faster-whisper`, `soundfile`

---

## File Structure

**Renderer (parallel-safe with Sub-project 1):**
- Create: `src/lib/dictation-modifiers.js` — mode constants, hotkey selector, voice-prefix parser, sayConfirmation()
- Create: `src/lib/__tests__/dictation-modifiers.test.js`
- Modify: `src/components/NoteView.jsx` — remove the mode picker, always-armed mic, both hotkeys live; hear-back on success
- Modify: `electron/preload.js` — expose `electronAPI.ttsSay(text)`
- Modify: `electron/main.js` — IPC handler `tts:say` fetches `/tts/say` and returns the WAV ArrayBuffer to the renderer

**Python service:**
- Create: `python-service/deepgram_client.py` — Nova-3 wrapper around `transcribe_file`
- Create: `python-service/faster_whisper_fallback.py` — local CPU fallback (small int8 model)
- Create: `python-service/tts_kokoro.py` — lazy Kokoro singleton + `synthesize_to_wav()`
- Create: `python-service/tests/test_deepgram_client.py`
- Create: `python-service/tests/test_tts_kokoro.py`
- Modify: `python-service/ai_client.py` — reroute `transcribe_audio()` through the chain; SACRED CONTENT in `_REWRITE_SYSTEM_PROMPT`
- Modify: `python-service/routes.py` — add `@app.get("/tts/say")`; default `mode` on `/transcribe-push-to-talk` is now `"rewrite"`
- Modify: `python-service/config.py` — `DEEPGRAM_API_KEY`, `KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`
- Modify: `python-service/requirements.txt` — add deepgram-sdk, kokoro-onnx, faster-whisper

**Docs:**
- Modify: `README.md` — DEEPGRAM_API_KEY env var, kokoro model paths, faster-whisper offline note

---

## Task 1 — Renderer: dictation-modifiers helper + tests

**Files:**
- Create: `src/lib/dictation-modifiers.js`
- Create: `src/lib/__tests__/dictation-modifiers.test.js`

- [ ] Step 1: Write tests covering mode constants, `pickDictationMode`, `parseVoicePrefix`
- [ ] Step 2: Run vitest, watch them fail
- [ ] Step 3: Implement helper with constants, hotkey detector, voice-prefix parser, sayConfirmation()
- [ ] Step 4: Re-run vitest, see all pass
- [ ] Step 5: Commit

## Task 2 — Renderer: NoteView panel collapse

**Files:**
- Modify: `src/components/NoteView.jsx` — drop the mode-picker buttons, render the armed mic permanently, listen for both hotkeys, call `sayConfirmation(note.title)` on append success

- [ ] Step 1: Strip the `dictationMode === null` branch; the mic is always armed
- [ ] Step 2: Replace the mode-selection state with a `lastModeRef` set by keydown
- [ ] Step 3: Add `Shift+Ctrl+Space` handler that sets the ref to `'verbatim'` before recording
- [ ] Step 4: After successful POST, call `sayConfirmation(note.title)`
- [ ] Step 5: `npm run typecheck` clean
- [ ] Step 6: Commit

## Task 3 — Electron: preload + main IPC for TTS

**Files:**
- Modify: `electron/preload.js`
- Modify: `electron/main.js`

- [ ] Step 1: preload exposes `ttsSay: (text) => ipcRenderer.invoke('tts:say', text)`
- [ ] Step 2: main registers `ipcMain.handle('tts:say', ...)` that fetches `http://localhost:8765/tts/say?text=...`, returns the ArrayBuffer (or empty buffer on failure — TTS must never crash the app)
- [ ] Step 3: typecheck clean
- [ ] Step 4: Commit

## Task 4 — Python: Deepgram Nova-3 client

**Files:**
- Create: `python-service/deepgram_client.py`
- Create: `python-service/tests/test_deepgram_client.py`

- [ ] Step 1: Write pytest with mocked `DeepgramClient` asserting `transcribe_file(request=bytes, model="nova-3", diarize=…)`
- [ ] Step 2: Implement `transcribe_with_deepgram(wav_bytes, with_speakers=False)` raising on failure
- [ ] Step 3: Run pytest, confirm pass
- [ ] Step 4: Commit

## Task 5 — Python: faster-whisper offline fallback

**Files:**
- Create: `python-service/faster_whisper_fallback.py`

- [ ] Step 1: Implement lazy `_get_model()` → `WhisperModel("small", device="cpu", compute_type="int8")`
- [ ] Step 2: Implement `transcribe_with_local_whisper(wav_bytes)` that writes to a temp WAV, transcribes, concatenates segments
- [ ] Step 3: Commit (manual smoke test deferred to verification step)

## Task 6 — Python: Kokoro TTS singleton + endpoint

**Files:**
- Create: `python-service/tts_kokoro.py`
- Create: `python-service/tests/test_tts_kokoro.py`
- Modify: `python-service/routes.py` — add `@app.get("/tts/say")`

- [ ] Step 1: Write pytest mocking `Kokoro.create()` and asserting WAV bytes start with `RIFF`
- [ ] Step 2: Implement `synthesize_to_wav(text, voice='af_heart') -> bytes` using `soundfile.write` to BytesIO
- [ ] Step 3: Add `@app.get("/tts/say")` returning `Response(content=wav, media_type="audio/wav")`
- [ ] Step 4: pytest pass
- [ ] Step 5: Commit

## Task 7 — Python: reroute `transcribe_audio` + sacred-content rules

**Files:**
- Modify: `python-service/ai_client.py`
- Modify: `python-service/config.py`

- [ ] Step 1: `config.py` — add `DEEPGRAM_API_KEY`, `KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`
- [ ] Step 2: `ai_client.py` — new `_chained_transcribe()` Deepgram → faster-whisper → legacy; wire into `transcribe_audio()`
- [ ] Step 3: Add SACRED CONTENT section to `_REWRITE_SYSTEM_PROMPT`
- [ ] Step 4: Default `/transcribe-push-to-talk` mode to `"rewrite"` in `routes.py`
- [ ] Step 5: Commit

## Task 8 — Dependencies + docs

**Files:**
- Modify: `python-service/requirements.txt`
- Modify: `README.md`

- [ ] Step 1: Append `deepgram-sdk>=5.0.0`, `kokoro-onnx`, `faster-whisper` to requirements.txt
- [ ] Step 2: README section "Dictation models" — DEEPGRAM_API_KEY env var, Kokoro model download path, faster-whisper offline note
- [ ] Step 3: Commit

## Task 9 — Verification & PR

- [ ] Step 1: `npm run typecheck`
- [ ] Step 2: `npm test`
- [ ] Step 3: `pytest python-service/tests -k 'deepgram or kokoro or modifiers'`
- [ ] Step 4: Document the manual hear-back smoke test in PR (`Hold Ctrl+Space → AI rewrite → hear "Saved to ..."`)
- [ ] Step 5: Open PR titled `feat(dictation): collapse modes + deepgram streaming + kokoro tts`

---

## Self-review notes

- **Spec coverage:** All five renderer-side items and five Python-side items from the prompt have at least one task. Out-of-scope items (voice routing grammar, structure-aware placement, canvas UI) are not present.
- **Parallel-safety:** Helper module isolates the dictation logic so Sub-project 1's eventual `InnerCanvas/TextCard` can swap NoteView's import with no rework. CSS in NoteView remains under existing classes — no new namespaces needed.
- **Fallback semantics:** Deepgram is best effort; on any non-200 or timeout the chain falls back. faster-whisper model defaults to `small` to keep first-launch download under 500 MB.
- **TTS failure surface:** TTS calls are fire-and-forget; never block the user-visible "saved" path.
