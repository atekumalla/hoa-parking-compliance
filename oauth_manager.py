"""
Google OAuth Manager for HOA Parking Compliance Tracker.

Handles per-user Google OAuth2 authentication flow within Streamlit.
Each user signs in with their own Google account to enable photo uploads
to Google Drive (uploads count against the authenticating user's quota).

Tokens are persisted in a browser cookie (base64-encoded JSON) so they
survive Render container restarts, deploys, and idle spin-downs.
The cookie has a 30-day max-age and stores the refresh_token which allows
silent re-authentication without user interaction.
"""

import base64
import json
import os
import urllib.parse
from typing import Optional

import requests
import streamlit as st
import streamlit.components.v1 as components
from google.oauth2.credentials import Credentials


# OAuth scopes needed for Drive file uploads
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Google OAuth endpoints
AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'


# ---------------------------------------------------------------------------
# Browser cookie helpers (persist full token across container restarts)
# ---------------------------------------------------------------------------

_COOKIE_NAME = 'hoa_parking_token'
_COOKIE_MAX_AGE_DAYS = 30


def _token_to_cookie_value(creds: Credentials) -> str:
    """Serialize credentials to a base64 string suitable for a cookie."""
    data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes) if creds.scopes else list(SCOPES),
    }
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _cookie_value_to_token(value: str) -> Optional[Credentials]:
    """Deserialize credentials from a base64 cookie value."""
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode()))
        if not data.get('refresh_token'):
            return None
        creds = Credentials(
            token=data.get('token'),
            refresh_token=data['refresh_token'],
            token_uri=data.get('token_uri', TOKEN_ENDPOINT),
            client_id=data.get('client_id'),
            client_secret=data.get('client_secret'),
            scopes=data.get('scopes', SCOPES),
        )
        # Refresh if expired
        if creds.expired or not creds.token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds
    except Exception:
        return None


def _inject_set_cookie_js(creds: Credentials):
    """Inject invisible JS to save the token as a browser cookie."""
    value = _token_to_cookie_value(creds)
    js = f"""
    <script>
    (function() {{
        var maxAge = {_COOKIE_MAX_AGE_DAYS} * 24 * 60 * 60;
        document.cookie = "{_COOKIE_NAME}=" + "{value}" + "; path=/; max-age=" + maxAge + "; SameSite=Lax";
    }})();
    </script>
    """
    components.html(js, height=0, width=0)


def _inject_clear_cookie_js():
    """Inject invisible JS to delete the session cookie."""
    js = f"""
    <script>
    (function() {{
        document.cookie = "{_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax";
    }})();
    </script>
    """
    components.html(js, height=0, width=0)


def _inject_restore_from_cookie_js():
    """
    Inject invisible JS that reads the token cookie and passes it back
    to the server via a query param so we can restore credentials.
    """
    js = f"""
    <script>
    (function() {{
        var params = new URLSearchParams(window.parent.location.search);
        // Don't interfere if token or code already present
        if (params.has('tkn') || params.has('code')) return;

        // Read cookie
        var match = document.cookie.match(/(^|;\\s*){_COOKIE_NAME}=([^;]+)/);
        if (match && match[2]) {{
            var tkn = match[2];
            // Pass token via query param for server-side restore
            var url = new URL(window.parent.location.href);
            url.searchParams.set('tkn', tkn);
            window.parent.location.replace(url.toString());
        }}
    }})();
    </script>
    """
    components.html(js, height=0, width=0)


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

        return creds

    except Exception as e:
        st.error(f"❌ OAuth token exchange failed: {str(e)}")
        return None


def get_user_credentials() -> Optional[Credentials]:
    """
    Get the current user's OAuth credentials.

    Checks session state first, then tries to restore from the browser
    cookie via the ?tkn= query param.

    Returns:
        Credentials object if authenticated, None otherwise.
    """
    creds = st.session_state.get('oauth_credentials')

    # If not in memory, try restoring from cookie token passed via query param
    if creds is None:
        tkn = st.query_params.get('tkn')
        if tkn:
            creds = _cookie_value_to_token(tkn)
            if creds:
                st.session_state['oauth_credentials'] = creds
                st.session_state['oauth_user_authenticated'] = True
                # Clear tkn from URL and persist updated cookie
                st.query_params.clear()
                _inject_set_cookie_js(creds)
                return creds
            else:
                # Cookie token invalid/expired — clear it
                st.query_params.clear()
                _inject_clear_cookie_js()
        return None

    # Check if credentials are expired and refresh if possible
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            st.session_state['oauth_credentials'] = creds
            # Update cookie with refreshed token
            _inject_set_cookie_js(creds)
        except Exception:
            # Refresh failed — user needs to re-authenticate
            st.session_state.pop('oauth_credentials', None)
            st.session_state.pop('oauth_user_authenticated', None)
            _inject_clear_cookie_js()
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
    After auth, the token is persisted in a browser cookie so credentials
    survive container restarts.
    """
    params = st.query_params
    code = params.get('code')

    if code and 'oauth_credentials' not in st.session_state:
        creds = exchange_code_for_credentials(code)
        if creds:
            st.session_state['oauth_credentials'] = creds
            st.session_state['oauth_user_authenticated'] = True
            # Clear code from URL and save token to cookie
            st.query_params.clear()
            _inject_set_cookie_js(creds)
        else:
            st.query_params.clear()
    elif 'oauth_credentials' in st.session_state:
        # Already authenticated — keep cookie fresh
        _inject_set_cookie_js(st.session_state['oauth_credentials'])
    else:
        # No active session — try to restore from browser cookie
        _inject_restore_from_cookie_js()


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
            _inject_clear_cookie_js()
            st.rerun()
    else:
        auth_url = get_authorization_url()
        st.warning("⚠️ Sign in with Google to enable photo uploads to Drive")
        st.link_button("🔐 Sign in with Google", auth_url)


def logout():
    """Clear OAuth credentials from session state and browser cookie."""
    st.session_state.pop('oauth_credentials', None)
    st.session_state.pop('oauth_user_authenticated', None)
    _inject_clear_cookie_js()
