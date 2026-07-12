"""
Google OAuth Manager for HOA Parking Compliance Tracker.

Handles per-user Google OAuth2 authentication flow within Streamlit.
Each user signs in with their own Google account to enable photo uploads
to Google Drive (uploads count against the authenticating user's quota).

Token persistence strategy:
- The refresh_token (long-lived, doesn't expire unless revoked) is stored
  in st.query_params (?rt=<base64>) so it persists in the URL across:
  * Page refreshes
  * Browser restarts
  * Mobile app kills
  * Render container restarts/deploys
- On each new session, the refresh_token is used to silently obtain a
  fresh access_token without user interaction.
- No filesystem, cookies, or JS injection required.
"""

import base64
import json
import os
import urllib.parse
from typing import Optional

import requests
import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# OAuth scopes needed for Drive file uploads
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Google OAuth endpoints
AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'


def _encode_refresh_token(refresh_token: str, client_id: str, client_secret: str) -> str:
    """Encode refresh token + client info to a URL-safe base64 string."""
    data = {
        'rt': refresh_token,
        'cid': client_id,
        'cs': client_secret,
    }
    return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).decode().rstrip('=')


def _decode_refresh_token(encoded: str) -> Optional[dict]:
    """Decode a base64 string back to refresh token + client info."""
    try:
        # Re-add padding
        padded = encoded + '=' * (4 - len(encoded) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if not data.get('rt'):
            return None
        return data
    except Exception:
        return None


def _refresh_credentials(refresh_token: str, client_id: str, client_secret: str) -> Optional[Credentials]:
    """Use a refresh_token to obtain fresh credentials."""
    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_ENDPOINT,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds
    except Exception:
        return None


def get_oauth_config() -> Optional[dict]:
    """Get OAuth client configuration from environment variables."""
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
    """Get the OAuth redirect URI."""
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI')
    if redirect_uri:
        return redirect_uri
    return 'http://localhost:8501'


def get_authorization_url() -> str:
    """Generate the Google OAuth authorization URL."""
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

    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_credentials(code: str) -> Optional[Credentials]:
    """Exchange an authorization code for OAuth credentials."""
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

        return creds

    except Exception as e:
        st.error(f"❌ OAuth token exchange failed: {str(e)}")
        return None


def get_user_credentials() -> Optional[Credentials]:
    """
    Get the current user's OAuth credentials.

    Checks session state first, then tries to restore from the ?rt= query param.
    """
    # 1. Already in memory for this session
    creds = st.session_state.get('oauth_credentials')
    if creds is not None:
        # Refresh if expired (access tokens last ~1 hour)
        if creds.expired or not creds.token:
            try:
                creds.refresh(Request())
                st.session_state['oauth_credentials'] = creds
            except Exception:
                # Refresh failed — clear everything
                st.session_state.pop('oauth_credentials', None)
                st.session_state.pop('oauth_user_authenticated', None)
                if 'rt' in st.query_params:
                    del st.query_params['rt']
                return None
        return creds

    # 2. Try restoring from ?rt= in URL (survives all restarts)
    rt_encoded = st.query_params.get('rt')
    if rt_encoded:
        token_data = _decode_refresh_token(rt_encoded)
        if token_data:
            creds = _refresh_credentials(
                token_data['rt'], token_data['cid'], token_data['cs']
            )
            if creds:
                st.session_state['oauth_credentials'] = creds
                st.session_state['oauth_user_authenticated'] = True
                return creds

        # Token invalid/revoked — clean up
        del st.query_params['rt']

    return None


def is_user_authenticated() -> bool:
    """Check if the current user has valid OAuth credentials."""
    return get_user_credentials() is not None


def handle_oauth_callback():
    """
    Handle the OAuth callback by checking for 'code' in query params.

    Called early in the app lifecycle. If a code is present, exchanges it
    for credentials, stores them in session state, and persists the
    refresh_token in the URL via st.query_params['rt'].
    """
    code = st.query_params.get('code')

    if code and 'oauth_credentials' not in st.session_state:
        creds = exchange_code_for_credentials(code)
        if creds:
            st.session_state['oauth_credentials'] = creds
            st.session_state['oauth_user_authenticated'] = True

            # Persist refresh_token in URL for long-term survival
            config = get_oauth_config()
            if creds.refresh_token and config:
                encoded = _encode_refresh_token(
                    creds.refresh_token, config['client_id'], config['client_secret']
                )
                st.query_params.clear()
                st.query_params['rt'] = encoded
            else:
                st.query_params.clear()
        else:
            st.query_params.clear()


def show_auth_ui():
    """Display the OAuth authentication UI component."""
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
            if 'rt' in st.query_params:
                del st.query_params['rt']
            st.rerun()
    else:
        auth_url = get_authorization_url()
        st.warning("⚠️ Sign in with Google to enable photo uploads to Drive")
        st.link_button("🔐 Sign in with Google", auth_url)


def logout():
    """Clear OAuth credentials from session state and URL."""
    st.session_state.pop('oauth_credentials', None)
    st.session_state.pop('oauth_user_authenticated', None)
    if 'rt' in st.query_params:
        del st.query_params['rt']
