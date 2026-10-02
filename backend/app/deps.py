"""Shared FastAPI dependencies."""
from typing import Optional

from fastapi import Request
from google.oauth2.credentials import Credentials

from . import oauth
from .state import state, AppState


def get_state() -> AppState:
    state.ensure_loaded()
    return state


def get_oauth_credentials(request: Request) -> Optional[Credentials]:
    return oauth.get_credentials(request)
