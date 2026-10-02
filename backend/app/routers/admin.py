"""Shared-passcode admin session — gates destructive actions only (see admin_auth.py)."""
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, Response

from .. import admin_auth

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginBody(BaseModel):
    passcode: str


@router.get("/status")
def admin_status(request: Request):
    return {
        "configured": admin_auth.is_configured(),
        "authenticated": admin_auth.is_authenticated(request),
        "photo_trusted": admin_auth.has_photo_trust(request),
    }


@router.post("/login")
def admin_login(body: LoginBody, request: Request, response: Response):
    admin_auth.check_login_rate_limit(request)
    if not admin_auth.verify_passcode(body.passcode):
        admin_auth.record_failed_login(request)
        raise HTTPException(401, "Incorrect passcode.")
    admin_auth.start_session(response)
    admin_auth.grant_photo_trust(response)
    return {"ok": True}


@router.post("/logout")
def admin_logout(request: Request, response: Response):
    admin_auth.end_session(request, response)
    return {"ok": True}
