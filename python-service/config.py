import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVICE_DIR = Path(__file__).resolve().parent
# Prefer the bundled .env that ships next to config.py (packaged installer).
# Fall back to repo-root .env so `npm run electron:dev` uses the source-of-truth file.
_bundled_env = SERVICE_DIR / ".env"
if _bundled_env.exists():
    load_dotenv(_bundled_env)
else:
    load_dotenv(ROOT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")

# Smart language routing: probe the first N seconds with OpenAI whisper-1 to
# detect language, then route to AssemblyAI (English — keeps keyterms +
# diarization) or OpenAI Whisper (everything else, incl. Arabic). Set to false
# to bypass and use AssemblyAI unconditionally.
SMART_ROUTING_ENABLED = os.getenv("SMART_ROUTING_ENABLED", "true").lower() == "true"
# Probe multiple windows and majority-vote — a single window can misclassify
# Quran recitation or other prosody-heavy audio (sustained vowels, tajweed).
# Duplicate offsets past the audio length are deduped at probe time.
LANGUAGE_PROBE_OFFSETS_SEC = [5, 60, 180]
LANGUAGE_PROBE_DURATION_SEC = 15

BUFFER_DURATION_SEC = int(os.getenv("BUFFER_DURATION_SEC", "600"))   # 10 min ring buffer
COMMAND_RECORD_SEC = 7
# After the VAD fix, this is a cap on *speech-seconds* sent to the transcriber,
# NOT wall-clock audio. main.py reads the full BUFFER_DURATION_SEC from the
# ring buffer, VAD trims it to speech-only, and note_generator caps the
# trimmed speech at this budget before transcription. A 60s YouTube Short
# now sends ~60s of speech; a 10-minute interview sends up to 5 min of speech.
SLICE_DURATION_SEC = int(os.getenv("SLICE_DURATION_SEC", "300"))

# ─── Voice Activity Detection (Silero-VAD) ───────────────────────────────────
# Silero-VAD thresholds. Defaults are the Silero-recommended values and work
# well on podcast/YouTube content. Tune via env if needed:
#   VAD_THRESHOLD          — probability threshold; 0.5 is balanced. Raise
#                            to 0.6-0.7 if background music/ambient is
#                            being classified as speech.
#   VAD_MIN_SPEECH_MS      — reject speech segments shorter than this.
#                            Filters breath/click artifacts.
#   VAD_MIN_SILENCE_MS     — silence shorter than this is merged into the
#                            surrounding speech segment (keeps natural
#                            pauses intact instead of chopping mid-sentence).
#   VAD_SPEECH_PAD_MS      — pad each side of a speech segment with this
#                            much extra audio so the transcriber doesn't
#                            lose onset consonants ("Sure" → "ure").
#   VAD_MAX_SPEECH_SEC     — hard ceiling on speech-seconds returned by
#                            extract_speech(). Safety net; the real budget
#                            is set per-call by the caller (usually
#                            SLICE_DURATION_SEC).
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))
VAD_MIN_SPEECH_MS = int(os.getenv("VAD_MIN_SPEECH_MS", "250"))
VAD_MIN_SILENCE_MS = int(os.getenv("VAD_MIN_SILENCE_MS", "400"))
VAD_SPEECH_PAD_MS = int(os.getenv("VAD_SPEECH_PAD_MS", "200"))
VAD_MAX_SPEECH_SEC = int(os.getenv("VAD_MAX_SPEECH_SEC", "600"))
# Real speech rarely exceeds ~3 words/sec. If the transcript exceeds this
# ratio against actual speech duration, the note is flagged as likely
# hallucinated (saved for review, not blocked — a warning only).
TRANSCRIPT_MAX_WORDS_PER_SEC = float(os.getenv("TRANSCRIPT_MAX_WORDS_PER_SEC", "3.5"))

SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.004"))
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", "3"))
MAX_COMMAND_SEC = int(os.getenv("MAX_COMMAND_SEC", "60"))
# If the user never starts talking after the wake word, give up after this many
# seconds and cancel the note (instead of recording dead air for MAX_COMMAND_SEC).
NO_SPEECH_TIMEOUT_SEC = float(os.getenv("NO_SPEECH_TIMEOUT_SEC", "8"))

SAMPLE_RATE = 16000
CHANNELS = 1

FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8765

WAKE_WORD_MODEL = str(SERVICE_DIR / "models" / "hey_deen.ppn")
# Porcupine sensitivity: 0.0 (fewer false positives) -> 1.0 (more sensitive).
# 0.5 is the Picovoice default. Bump to 0.6-0.7 if "Hey Deen" is missed often.
PORCUPINE_SENSITIVITY = float(os.getenv("PORCUPINE_SENSITIVITY", "0.6"))

MEDIA_DETECT_THRESHOLD = float(os.getenv("MEDIA_DETECT_THRESHOLD", "0.005"))

# Where klippa.db and pending/ live. Electron passes DEEN_NOTES_DATA_DIR
# pointing at app.getPath('userData') in packaged mode so user notes survive
# uninstall/reinstall. In `npm run electron:dev` no env var is set and we
# fall back to ROOT_DIR so the existing dev-time klippa.db keeps working.
_data_dir_env = os.getenv("DEEN_NOTES_DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir_env) if _data_dir_env else ROOT_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

# DB filename kept as klippa.db to preserve existing notes from before the rename.
# Don't change this without writing a migration.
DB_PATH = DATA_DIR / "klippa.db"
PENDING_DIR = DATA_DIR / "pending"
PENDING_DIR.mkdir(exist_ok=True)
