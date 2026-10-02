"""
Shared-passcode gate for destructive actions (add/delete entries, delete
photos, force-refresh). Deliberately simple — one passcode for the whole
patrol team, not per-user identity. Reads are never gated by this.

Session model mirrors oauth.py's cookie approach: an opaque signed session id
in an httpOnly cookie, Credentials-equivalent (here just a boolean) kept
server-side. No passcode or secret ever reaches the browser.
"""
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature

from . import config

ADMIN_COOKIE = "admin_sid"
_SESSION_MAX_AGE = timedelta(hours=12)
_serializer = URLSafeTimedSerializer(config.SESSION_SECRET_KEY, salt="admin-session")

# session_id -> last_used_at
_SESSIONS: Dict[str, datetime] = {}

# Separate, longer-lived cookie granted alongside a successful admin login.
# Gates only the paid OpenAI analyze-photo call (cost/abuse control, not data
# destruction) so a device doesn't need the passcode re-entered constantly.
# Stateless (no server-side session dict needed — low stakes if leaked) and
# slides forward on every use, so an actively-used device stays trusted
# indefinitely while an idle/stolen one re-locks after a week of inactivity.
PHOTO_TRUST_COOKIE = "photo_trust"
_PHOTO_TRUST_MAX_AGE = timedelta(days=7)
_photo_trust_serializer = URLSafeTimedSerializer(config.SESSION_SECRET_KEY, salt="photo-trust")

# Brute-force throttling on /api/admin/login, keyed by client IP.
_MAX_FAILED_ATTEMPTS = 5
_ATTEMPT_WINDOW = timedelta(minutes=15)
_FAILED_ATTEMPTS: Dict[str, List[datetime]] = {}


def is_configured() -> bool:
    return bool(config.ADMIN_PASSCODE)


def _sweep_expired() -> None:
    cutoff = datetime.now() - _SESSION_MAX_AGE
    # Snapshot with list() — concurrent requests may mutate _SESSIONS while
    # we iterate, which would raise RuntimeError otherwise.
    expired = [sid for sid, last_used in list(_SESSIONS.items()) if last_used < cutoff]
    for sid in expired:
        _SESSIONS.pop(sid, None)


def verify_passcode(passcode: str) -> bool:
    if not config.ADMIN_PASSCODE:
        return False
    # Constant-time comparison — a naive `==` leaks timing information an
    # attacker could use to guess the passcode character-by-character.
    return hmac.compare_digest(passcode, config.ADMIN_PASSCODE)


def start_session(response: Response) -> None:
    _sweep_expired()
    session_id = secrets.token_urlsafe(32)
    _SESSIONS[session_id] = datetime.now()
    signed = _serializer.dumps(session_id)
    response.set_cookie(
        ADMIN_COOKIE,
        signed,
        httponly=True,
        samesite="lax",
        secure=config.IS_PROD,
        max_age=int(_SESSION_MAX_AGE.total_seconds()),
        path="/",
    )


def end_session(request: Request, response: Response) -> None:
    session_id = _read_session_id(request)
    if session_id:
        _SESSIONS.pop(session_id, None)
    response.delete_cookie(ADMIN_COOKIE, path="/")
    # Photo trust is deliberately left intact — "Lock" protects destructive
    # actions, it isn't meant to force re-entering the passcode for analysis.


def grant_photo_trust(response: Response) -> None:
    token = _photo_trust_serializer.dumps("trusted")
    response.set_cookie(
        PHOTO_TRUST_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=config.IS_PROD,
        max_age=int(_PHOTO_TRUST_MAX_AGE.total_seconds()),
        path="/",
    )


def has_photo_trust(request: Request) -> bool:
    token = request.cookies.get(PHOTO_TRUST_COOKIE)
    if not token:
        return False
    try:
        _photo_trust_serializer.loads(token, max_age=_PHOTO_TRUST_MAX_AGE.total_seconds())
        return True
    except BadSignature:
        return False


def _read_session_id(request: Request):
    signed = request.cookies.get(ADMIN_COOKIE)
    if not signed:
        return None
    try:
        return _serializer.loads(signed, max_age=_SESSION_MAX_AGE.total_seconds())
    except BadSignature:
        return None


def is_authenticated(request: Request) -> bool:
    session_id = _read_session_id(request)
    if not session_id or session_id not in _SESSIONS:
        return False
    _SESSIONS[session_id] = datetime.now()  # touch last-used
    return True


def require_admin(request: Request) -> None:
    """FastAPI dependency — raises 401 unless the shared passcode has been entered."""
    if not is_configured():
        raise HTTPException(503, "Destructive actions are disabled: ADMIN_PASSCODE is not configured.")
    if not is_authenticated(request):
        raise HTTPException(401, "Admin unlock required — enter the passcode first.")


def require_photo_trust(request: Request, response: Response) -> None:
    """FastAPI dependency for /api/analyze-photo — gates the paid OpenAI call
    behind the same passcode, but with its own 7-day sliding cookie instead of
    the 12h destructive-action session."""
    if not is_configured():
        raise HTTPException(503, "Photo analysis is disabled: ADMIN_PASSCODE is not configured.")
    if not has_photo_trust(request):
        raise HTTPException(401, "This device hasn't been unlocked. Enter the admin passcode once to enable photo analysis.")
    grant_photo_trust(response)  # slide the 7-day window forward


def _client_ip(request: Request) -> str:
    # Best-effort: behind Render's proxy the real client is the first hop in
    # X-Forwarded-For. Not spoof-proof, but good enough to slow down casual
    # brute-forcing — the passcode's constant-time check is the real gate.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login_rate_limit(request: Request) -> None:
    """Raises 429 if this client has failed too many login attempts recently."""
    ip = _client_ip(request)
    cutoff = datetime.now() - _ATTEMPT_WINDOW
    attempts = [t for t in _FAILED_ATTEMPTS.get(ip, []) if t > cutoff]
    _FAILED_ATTEMPTS[ip] = attempts
    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        raise HTTPException(429, "Too many incorrect attempts. Try again in 15 minutes.")


def record_failed_login(request: Request) -> None:
    ip = _client_ip(request)
    _FAILED_ATTEMPTS.setdefault(ip, []).append(datetime.now())
