"""Central configuration for ADAPT-IQ. All switches are environment-driven."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_PATH = BASE_DIR / "src" / "ml" / "model.joblib"
SETTINGS_PATH = DATA_DIR / "student_settings.json"

# "csv" (default, works out of the box) or "gsheet" (needs credentials)
DATA_SOURCE = os.getenv("DATA_SOURCE", "csv").lower()
CSV_PATH = Path(os.getenv("CSV_PATH", DATA_DIR / "synthetic_responses.csv"))

# Google Sheets mode (untested against live credentials — see README)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "")
GSHEET_NAME = os.getenv("GSHEET_NAME", "ADAPT-IQ Responses")
GSHEET_WORKSHEET = os.getenv("GSHEET_WORKSHEET", "Form Responses 1")

# --- AI enhancement (all optional; app is fully functional without) ---
# AI_PROVIDER: gemini | groq | openrouter | ollama | (empty = off)
AI_PROVIDER = os.getenv("AI_PROVIDER", "").lower()
AI_API_KEY = os.getenv("AI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")           # empty = provider default
# Optional second provider tried automatically when the primary fails
# (e.g. AI_FALLBACK_PROVIDER=groq with its own key) — removes 429 hiccups.
AI_FALLBACK_PROVIDER = os.getenv("AI_FALLBACK_PROVIDER", "").lower()
AI_FALLBACK_KEY = os.getenv("AI_FALLBACK_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# back-compat: a bare GEMINI_API_KEY implies the gemini provider
if not AI_PROVIDER and os.getenv("GEMINI_API_KEY"):
    AI_PROVIDER = "gemini"

# Live resource fetching (Wikipedia API, keyless). Set "0" to force offline.
LIVE_RESOURCES = os.getenv("LIVE_RESOURCES", "1") != "0"

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "adapt-iq-dev-key")
