"""Application configuration, loaded from the repo-root .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Reuse the same .env the Streamlit app used to avoid duplicating secrets.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Resolve a relative credentials path against the repo root so this works
# regardless of the process's current working directory (e.g. `cd backend`).
_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if _creds_path and not os.path.isabs(_creds_path):
    _creds_path = str(_REPO_ROOT / _creds_path)
GOOGLE_CREDENTIALS_PATH = _creds_path

SCOREBOARD_TOP_N = int(os.getenv("SCOREBOARD_TOP_N", "20"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback")

# Signs the "sid" session cookie. Set SESSION_SECRET_KEY in .env for prod;
# falls back to a fixed dev value so local runs don't need extra setup.
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-only-insecure-secret-change-me")

# Frontend origin allowed to receive cookies in local dev (Vite proxies /api
# so requests are same-origin from the browser's perspective — this is only
# used for the OAuth redirect target).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# How long the shared in-memory data cache stays fresh before a background refresh.
DATA_CACHE_TTL_SECONDS = int(os.getenv("DATA_CACHE_TTL_SECONDS", "300"))

IS_PROD = os.getenv("RENDER", "") != "" or os.getenv("ENV", "").lower() == "production"

if IS_PROD and os.getenv("SESSION_SECRET_KEY") is None:
    raise RuntimeError(
        "SESSION_SECRET_KEY is not set. Refusing to start in production with the "
        "default dev signing key — set it in the environment."
    )

# Shared passcode gating destructive actions (add/delete entries, delete
# photos, force-refresh). Reads are intentionally left open. Unset = those
# routes are disabled entirely rather than silently left unprotected.
ADMIN_PASSCODE = os.getenv("ADMIN_PASSCODE")
