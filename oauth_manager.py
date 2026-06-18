"""
Google OAuth Manager for HOA Parking Compliance Tracker.

Handles per-user Google OAuth2 authentication flow within Streamlit.
Each user signs in with their own Google account to enable photo uploads
to Google Drive (uploads count against the authenticating user's quota).

Tokens are persisted to disk so users don't need to re-login on every
page refresh. The token file survives server restarts (lost on redeploy).
"""

import os
import json
import urllib.parse
from typing import Optional

import requests
import streamlit as st
from google.oauth2.credentials import Credentials


# OAuth scopes needed for Drive file uploads
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Google OAuth endpoints
AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'

# File to persist OAuth tokens across page refreshes
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.oauth_tokens.json')


def get_oauth_config() -> Optional[dict]:
    """
    Get OAuth client configuration from environment variables.

    Returns:
        Dict with client_id, client_secret, redirect_uri or None if not configured.
    """
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

    if not client_id or not client_secret:
        return None

    return {
        'client_id': client_id,
        'client_secret': client_secret,
    }


def is_oauth_configured() -> bool:
    """Check if OAuth credentials are configured in environment."""
    return get_oauth_config() is not None


def get_redirect_uri() -> str:
    """
    Get the OAuth redirect URI.

    Uses GOOGLE_OAUTH_REDIRECT_URI env var, or falls back to localhost.
    """
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI')
    if redirect_uri:
        return redirect_uri
    return 'http://localhost:8501'


def _save_token_to_disk(creds: Credentials):
    """Save OAuth credentials to disk for persistence across page refreshes."""
    try:
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': list(creds.scopes) if creds.scopes else list(SCOPES),
        }
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
    except Exception:
        pass  # Best effort — if we can't save, user just re-auths next refresh


def _load_token_from_disk() -> Optional[Credentials]:
    """Load OAuth credentials from disk if available."""
    try:
        if not os.path.exists(TOKEN_FILE):
            return None

        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)

        if not token_data.get('refresh_token'):
            return None

        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data['refresh_token'],
            token_uri=token_data.get('token_uri', TOKEN_ENDPOINT),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=token_data.get('scopes', SCOPES),
        )

        # Try to refresh if expired
        if creds.expired or not creds.token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            _save_token_to_disk(creds)  # Save updated access token

        return creds

    except Exception:
        # Token file is corrupt or refresh failed — delete it
        try:
            os.remove(TOKEN_FILE)
        except Exception:
            pass
        return None


def _delete_token_from_disk():
    """Remove the persisted token file."""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass


def get_authorization_url() -> str:
    """
    Generate the Google OAuth authorization URL manually (no PKCE).

    Returns:
        URL string that the user should visit to authorize.
    """
    config = get_oauth_config()
    redirect_uri = get_redirect_uri()

    params = {
        'client_id': config['client_id'],
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
    }

    auth_url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"
    return auth_url


def exchange_code_for_credentials(code: str) -> Optional[Credentials]:
    """
    Exchange an authorization code for OAuth credentials via HTTP POST.

    No PKCE code_verifier — uses client_secret for security instead.

    Args:
        code: The authorization code from Google's redirect.

    Returns:
        Google OAuth Credentials object, or None on failure.
    """
    config = get_oauth_config()
    redirect_uri = get_redirect_uri()

    try:
        response = requests.post(TOKEN_ENDPOINT, data={
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        })

        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
            st.error(f"❌ OAuth token exchange failed: {error_msg}")
            return None

        token_data = response.json()

        creds = Credentials(
            token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            token_uri=TOKEN_ENDPOINT,
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            scopes=SCOPES,
        )

        # Persist to disk so it survives page refreshes
        _save_token_to_disk(creds)

        return creds

    except Exception as e:
        st.error(f"❌ OAuth token exchange failed: {str(e)}")
        return None


def get_user_credentials() -> Optional[Credentials]:
    """
    Get the current user's OAuth credentials.

    Checks session state first, then falls back to disk-persisted token.

    Returns:
        Credentials object if authenticated, None otherwise.
    """
    creds = st.session_state.get('oauth_credentials')

    # If nothing in session state, try loading from disk (e.g. after page refresh)
    if creds is None:
        creds = _load_token_from_disk()
        if creds:
            st.session_state['oauth_credentials'] = creds
            st.session_state['oauth_user_authenticated'] = True
            return creds
        return None

    # Check if credentials are expired and refresh if possible
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            st.session_state['oauth_credentials'] = creds
            _save_token_to_disk(creds)  # Persist refreshed token
        except Exception:
            # Refresh failed — user needs to re-authenticate
            st.session_state.pop('oauth_credentials', None)
            _delete_token_from_disk()
            return None

    return creds


def is_user_authenticated() -> bool:
    """Check if the current user has valid OAuth credentials."""
    return get_user_credentials() is not None


def handle_oauth_callback():
    """
    Handle the OAuth callback by checking for 'code' in query params.

    Should be called early in the app lifecycle. If a code is present,
    it exchanges it for credentials and stores them in session state.
    """
    params = st.query_params
    code = params.get('code')

    if code and 'oauth_credentials' not in st.session_state:
        creds = exchange_code_for_credentials(code)
        if creds:
            st.session_state['oauth_credentials'] = creds
            st.session_state['oauth_user_authenticated'] = True
        # Clear the code from URL to prevent re-processing
        st.query_params.clear()


def show_auth_ui():
    """
    Display the OAuth authentication UI component.

    Shows either a "Sign in" button or the authenticated status.
    """
    if not is_oauth_configured():
        st.warning(
            "⚠️ Google OAuth not configured. Photo uploads are disabled. "
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in your .env file."
        )
        return

    if is_user_authenticated():
        st.success("✅ Signed in to Google — photo uploads enabled")
        if st.button("🚪 Sign out", key="oauth_signout"):
            st.session_state.pop('oauth_credentials', None)
            st.session_state.pop('oauth_user_authenticated', None)
            _delete_token_from_disk()
            st.rerun()
    else:
        auth_url = get_authorization_url()
        st.warning("⚠️ Sign in with Google to enable photo uploads to Drive")
        st.link_button("🔐 Sign in with Google", auth_url)


def logout():
    """Clear OAuth credentials from session state and disk."""
    st.session_state.pop('oauth_credentials', None)
    st.session_state.pop('oauth_user_authenticated', None)
    _delete_token_from_disk()
