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
```

Get a free Picovoice access key at https://console.picovoice.ai/. The "Hey Deen"
wake-word file (`python-service/models/hey_deen.ppn`) ships with the repo and is
trained for Windows. If you train your own keyword, replace that file.

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
- **OpenAI Whisper** — Audio transcription
- **OpenAI GPT-4o mini** — Note generation
- **SQLite** — Local note storage
