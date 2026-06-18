#!/usr/bin/env python3
"""
One-time OAuth Setup Helper

This script helps you set up Google OAuth credentials for the HOA Parking app.
Run this locally ONCE to verify your OAuth client configuration works.

Prerequisites:
1. Go to Google Cloud Console: https://console.cloud.google.com
2. Select your project (same one as your service account)
3. Go to APIs & Services > Credentials
4. Click "Create Credentials" > "OAuth client ID"
5. Application type: "Web application"
6. Name: "HOA Parking App"
7. Authorized redirect URIs:
   - http://localhost:8501 (for local dev)
   - https://your-app.onrender.com (for production)
8. Copy the Client ID and Client Secret to your .env file

Usage:
    python auth_setup.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def check_config():
    """Verify OAuth configuration."""
    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

    print("=" * 60)
    print("  HOA Parking - Google OAuth Setup Checker")
    print("=" * 60)
    print()

    if not client_id:
        print("❌ GOOGLE_OAUTH_CLIENT_ID not found in .env")
        print()
        print("   To set this up:")
        print("   1. Go to https://console.cloud.google.com/apis/credentials")
        print("   2. Create an OAuth 2.0 Client ID (Web application type)")
        print("   3. Add redirect URIs:")
        print("      - http://localhost:8501")
        print("      - https://your-app.onrender.com")
        print("   4. Copy the Client ID to .env as GOOGLE_OAUTH_CLIENT_ID")
        print()
        return False

    if not client_secret:
        print("❌ GOOGLE_OAUTH_CLIENT_SECRET not found in .env")
        print("   Copy it from the OAuth client you created in GCP Console.")
        print()
        return False

    print(f"✅ Client ID: {client_id[:20]}...{client_id[-10:]}")
    print(f"✅ Client Secret: {client_secret[:5]}...{client_secret[-5:]}")
    print()

    # Check redirect URI
    redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8501')
    print(f"📌 Redirect URI: {redirect_uri}")
    print()
    print("   Make sure this EXACT URI is listed in your OAuth client's")
    print("   'Authorized redirect URIs' in GCP Console.")
    print()

    # Check Drive API is enabled
    print("📋 Checklist:")
    print("   [ ] Google Drive API is enabled for your project")
    print("   [ ] OAuth consent screen is configured (Testing mode is fine)")
    print("   [ ] Your email is added as a test user on the consent screen")
    print(f"   [ ] Redirect URI '{redirect_uri}' is in authorized URIs")
    print()

    return True


def test_auth_url():
    """Generate a test authorization URL."""
    try:
        from oauth_manager import get_authorization_url, create_auth_flow
        # We can't fully test without Streamlit session, but we can build the URL
        from google_auth_oauthlib.flow import Flow

        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8501')

        client_config = {
            'web': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [redirect_uri],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/drive.file'],
            redirect_uri=redirect_uri
        )

        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        print("✅ OAuth flow created successfully!")
        print()
        print("🔗 Test authorization URL (open in browser to verify):")
        print(f"   {auth_url}")
        print()
        print("   If this opens Google's consent screen, your OAuth is configured correctly.")
        print("   You don't need to complete the sign-in here — the app will handle it.")
        print()
        return True

    except Exception as e:
        print(f"❌ Error creating OAuth flow: {e}")
        return False


if __name__ == '__main__':
    if check_config():
        test_auth_url()
    else:
        print("Fix the issues above, then run this script again.")
        sys.exit(1)

    print("=" * 60)
    print("  Setup looks good! Run your Streamlit app:")
    print("  streamlit run app.py")
    print("=" * 60)
