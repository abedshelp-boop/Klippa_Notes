import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

BUFFER_DURATION_SEC = int(os.getenv("BUFFER_DURATION_SEC", "120"))
COMMAND_RECORD_SEC = 7
SLICE_DURATION_SEC = 90

SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.01"))
SILENCE_DURATION_SEC = float(os.getenv("SILENCE_DURATION_SEC", "3"))
MAX_COMMAND_SEC = int(os.getenv("MAX_COMMAND_SEC", "120"))

SAMPLE_RATE = 16000
CHANNELS = 1

FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8765

WAKE_WORD_MODEL = str(SERVICE_DIR / "models" / "hey_klippa.onnx")
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.2"))
WAKE_WORD_PEAK_THRESHOLD = float(os.getenv("WAKE_WORD_PEAK_THRESHOLD", "0.5"))
MIC_GAIN = float(os.getenv("MIC_GAIN", "1.5"))

MEDIA_DETECT_THRESHOLD = float(os.getenv("MEDIA_DETECT_THRESHOLD", "0.005"))

ARABIZE_ENABLED = os.getenv("ARABIZE_ENABLED", "true").lower() == "true"

DB_PATH = ROOT_DIR / "klippa.db"
PENDING_DIR = ROOT_DIR / "pending"
PENDING_DIR.mkdir(exist_ok=True)
