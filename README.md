# Deen-Notes

Voice-activated note-taking app. Say **"Hey Deen"** while listening to a podcast, lecture, or video, and it captures what was said and generates a beautifully structured note.

## How It Works

1. System audio is continuously captured via WASAPI loopback (last 2 minutes buffered)
2. Your microphone listens for the wake word "Hey Deen" using Picovoice Porcupine
3. When triggered, the audio is sent to OpenAI Whisper for transcription
4. GPT-4o mini generates a structured Markdown note from the transcript
5. The note appears in the app with full formatting

## Quick Start

### Prerequisites

- Node.js 20+ and Python 3.11+ installed
- An OpenAI API key

### Setup

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies (from the python-service folder)
cd python-service
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
cd ..
```

### Configure

Edit the `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
PICOVOICE_ACCESS_KEY=your-picovoice-key-here
# Sub-project 4 — primary transcriber. If unset the chain falls straight to
# the offline faster-whisper fallback (slower first call, no quality loss).
DEEPGRAM_API_KEY=dg-your-key-here
```

Get a free Picovoice access key at https://console.picovoice.ai/. The "Hey Deen"
wake-word file (`python-service/models/hey_deen.ppn`) ships with the repo and is
trained for Windows. If you train your own keyword, replace that file.

### Dictation models (Sub-project 4)

Push-to-talk and the "Hey Deen" capture run through a three-tier transcription chain:

1. **Deepgram Nova-3** (`DEEPGRAM_API_KEY`) — default; multilingual; diarization on demand.
2. **faster-whisper** ("small" int8 on CPU) — automatic offline fallback. First call
   downloads ~480 MB of model weights to `%USERPROFILE%\.cache\huggingface\…`;
   subsequent calls are fully offline. Override with `FASTER_WHISPER_MODEL_SIZE=base`
   if you want a smaller model or `medium` / `large-v3` if you want more accuracy.
3. **OpenAI / AssemblyAI** — final safety net if neither of the above is configured;
   uses the same env vars as before.

Hear-back confirmations ("Saved to *Sapiens*") use **Kokoro TTS** running locally:

- Install: covered by `pip install -r python-service/requirements.txt` (pulls
  `kokoro-onnx`).
- Voice + model files (large binaries — not in git):
  - `python-service/models/kokoro-v1.0.onnx`
  - `python-service/models/voices-v1.0.bin`
  
  Download from `https://github.com/thewh1teagle/kokoro-onnx/releases` and drop them
  into `python-service/models/`. Override locations with `KOKORO_MODEL_PATH` /
  `KOKORO_VOICES_PATH` env vars if you want them somewhere shared. Override the
  voice with `KOKORO_VOICE` (default: `af_heart`, the warm friendly voice).

Dictation hotkeys inside an open note:
- `Ctrl+Space` (hold) → **AI Rewrite** (default — restructures + applies sacred-content rules).
- `Shift+Ctrl+Space` (hold) → **Verbatim** (filler stripped, every meaningful word preserved).
- Voice prefix `"quote: ..."` / `"verbatim: ..."` flips to verbatim mid-utterance.

### Run

```bash
npm run electron:dev
```

This starts the Vite dev server, waits for it to be ready, then launches Electron (which spawns the Python backend automatically).

## Tech Stack

- **Electron + React + Vite** — Desktop app and UI
- **Python + FastAPI** — Audio capture, AI pipeline, and REST/WebSocket API
- **pyaudiowpatch** — WASAPI loopback for system audio capture
- **Picovoice Porcupine** — Wake word detection ("Hey Deen")
- **Deepgram Nova-3** — Primary transcription (multilingual, diarization)
- **faster-whisper** — Offline transcription fallback (CPU, int8)
- **Kokoro TTS (ONNX)** — Local hear-back confirmations
- **OpenAI GPT-4.1** — Note generation
- **SQLite** — Local note storage
