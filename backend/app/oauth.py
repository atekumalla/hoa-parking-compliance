"""
Google OAuth for per-user Drive uploads.

Security improvement over the old Streamlit version: the refresh token never
leaves the server. The browser only holds an opaque, signed session id in an
httpOnly cookie; the actual Credentials object lives in server memory keyed
by that id. This avoids ever exposing OAuth tokens to JS/localStorage.

Known limitation: the session store is in-process memory, so a backend
restart requires users to sign in again. Acceptable for this app's scale;
swap for Redis/DB-backed storage if that becomes a problem.
"""
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import requests
from fastapi import Request, Response
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from itsdangerous import URLSafeTimedSerializer, BadSignature

from . import config

SCOPES = ['https://www.googleapis.com/auth/drive.file']
AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'

SESSION_COOKIE = "sid"
_serializer = URLSafeTimedSerializer(config.SESSION_SECRET_KEY, salt="oauth-session")

# Sessions unused for this long are dropped — keeps the store from growing
# forever across a long-running process (matches the cookie's 30-day max_age).
_SESSION_MAX_AGE = timedelta(days=30)

# session_id -> (credentials, last_used_at)
_SESSIONS: Dict[str, Tuple[Credentials, datetime]] = {}


def _sweep_expired_sessions() -> None:
    cutoff = datetime.now() - _SESSION_MAX_AGE
    # Snapshot with list() — this runs while other requests may concurrently
    # touch _SESSIONS, and iterating a dict while it's mutated raises RuntimeError.
    expired = [sid for sid, (_, last_used) in list(_SESSIONS.items()) if last_used < cutoff]
    for sid in expired:
        _SESSIONS.pop(sid, None)


# -- Login CSRF protection (state parameter) --
# A short-lived nonce round-tripped through Google's redirect. Without this,
# an attacker can initiate their own OAuth flow, trick a victim into
# completing it, and bind the victim's app session to the attacker's Google
# account (so the victim's uploads silently land in the attacker's Drive).
STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 600  # 10 minutes — just long enough to complete the Google consent screen


def new_state_nonce() -> str:
    return secrets.token_urlsafe(24)


def verify_and_clear_state(request: Request, received_state: Optional[str]) -> bool:
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not cookie_state or not received_state:
        return False
    return hmac.compare_digest(cookie_state, received_state)


def is_oauth_configured() -> bool:
    return bool(config.GOOGLE_OAUTH_CLIENT_ID and config.GOOGLE_OAUTH_CLIENT_SECRET)


def get_authorization_url(state: str) -> str:
    params = {
        'client_id': config.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': config.GOOGLE_OAUTH_REDIRECT_URI,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    }
    import urllib.parse
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_credentials(code: str) -> Optional[Credentials]:
    response = requests.post(TOKEN_ENDPOINT, data={
        'code': code,
        'client_id': config.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': config.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': config.GOOGLE_OAUTH_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }, timeout=10)

    if response.status_code != 200:
        return None

    token_data = response.json()
    return Credentials(
        token=token_data['access_token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=TOKEN_ENDPOINT,
        client_id=config.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=config.GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=SCOPES,
    )


def start_session(creds: Credentials, response: Response) -> None:
    _sweep_expired_sessions()
    session_id = secrets.token_urlsafe(32)
    _SESSIONS[session_id] = (creds, datetime.now())
    signed = _serializer.dumps(session_id)
    response.set_cookie(
        SESSION_COOKIE,
        signed,
        httponly=True,
        samesite="lax",
        secure=config.IS_PROD,
        max_age=60 * 60 * 24 * 30,  # 30 days — refresh_token is long-lived
        path="/",
    )


def end_session(request: Request, response: Response) -> None:
    session_id = _read_session_id(request)
    if session_id:
        _SESSIONS.pop(session_id, None)
    response.delete_cookie(SESSION_COOKIE, path="/")


def _read_session_id(request: Request) -> Optional[str]:
    signed = request.cookies.get(SESSION_COOKIE)
    if not signed:
        return None
    try:
        return _serializer.loads(signed, max_age=60 * 60 * 24 * 30)
    except BadSignature:
        return None


def get_credentials(request: Request) -> Optional[Credentials]:
    """Return valid (refreshed if needed) credentials for the current session, or None."""
    session_id = _read_session_id(request)
    if not session_id:
        return None
    entry = _SESSIONS.get(session_id)
    if entry is None:
        return None
    creds, _ = entry
    if creds.expired or not creds.token:
        try:
            creds.refresh(GoogleAuthRequest())
        except Exception:
            _SESSIONS.pop(session_id, None)
            return None
    _SESSIONS[session_id] = (creds, datetime.now())  # touch last-used
    return creds


def is_authenticated(request: Request) -> bool:
    return get_credentials(request) is not None
