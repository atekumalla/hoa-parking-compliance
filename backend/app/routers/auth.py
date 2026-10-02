"""OAuth sign-in endpoints (per-user Drive upload authorization)."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from .. import oauth
from .. import config

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status(request: Request):
    return {
        "configured": oauth.is_oauth_configured(),
        "authenticated": oauth.is_authenticated(request),
    }


@router.get("/login")
def auth_login():
    if not oauth.is_oauth_configured():
        return RedirectResponse(url=f"{config.FRONTEND_URL}?auth_error=not_configured")
    state_nonce = oauth.new_state_nonce()
    redirect = RedirectResponse(url=oauth.get_authorization_url(state_nonce))
    redirect.set_cookie(
        oauth.STATE_COOKIE, state_nonce,
        httponly=True, samesite="lax", secure=config.IS_PROD,
        max_age=oauth.STATE_MAX_AGE, path="/",
    )
    return redirect


@router.get("/callback")
def auth_callback(request: Request, code: str = None, error: str = None, state: str = None):
    if error or not code:
        return RedirectResponse(url=f"{config.FRONTEND_URL}?auth_error=denied")

    if not oauth.verify_and_clear_state(request, state):
        return RedirectResponse(url=f"{config.FRONTEND_URL}?auth_error=state_mismatch")

    creds = oauth.exchange_code_for_credentials(code)
    if not creds:
        return RedirectResponse(url=f"{config.FRONTEND_URL}?auth_error=exchange_failed")

    redirect = RedirectResponse(url=config.FRONTEND_URL)
    redirect.delete_cookie(oauth.STATE_COOKIE, path="/")
    oauth.start_session(creds, redirect)
    return redirect


@router.post("/logout")
def auth_logout(request: Request, response: Response):
    oauth.end_session(request, response)
    return {"ok": True}
