import os
from pathlib import Path


def _load_dotenv(path=".env"):
    """Minimal .env loader: KEY=VALUE lines; existing env vars win."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "invoice_desk.db"
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB") or 5)
AMOUNT_THRESHOLD = float(os.environ.get("AMOUNT_THRESHOLD") or 10000)
TOLERANCE = float(os.environ.get("TOLERANCE") or 0.02)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "").strip()
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "").strip() or os.urandom(24).hex()
BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "").strip()
BASIC_AUTH_PASS = os.environ.get("BASIC_AUTH_PASS", "")
