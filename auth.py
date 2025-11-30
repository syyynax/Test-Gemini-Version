import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Configuration
# We request read-only access to the user's calendar to ensure we don't accidentally modify events.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# --- APP URL ---
# This URL must match exactly what is configured in the Google Cloud Console.
# It is the address where users are sent back after logging in.
REDIRECT_URI = "https://meetly-augzgdgermpiwnemrvgyuv.streamlit.app"

def get_google_service():
    """
    Handles the entire OAuth2 login flow.
    It attempts to read credentials from Streamlit Secrets first (for production),
    and falls back to a local JSON file (for local development).
    """
    # 1. Check Session State
    # If the user is already logged in during this session, we don't need to authenticate again.
    if "credentials" not in st.session_state:
        st.session_state.credentials = None

    # If valid credentials exist, build and return the API service immediately.
    if st.session_state.credentials:
        return build("calendar", "v3", credentials=st.session_state.credentials)

    # 2. Start Login Flow
    flow = None
    
    # Strategy A: Load Secrets from Streamlit Cloud (Production)
    # We check if the specific secret structure 'GOOGLE_OAUTH_CLIENT' exists.
    secrets_data = None
    if "GOOGLE_OAUTH_CLIENT" in st.secrets and "web" in st.secrets["GOOGLE_OAUTH_CLIENT"]:
        secrets_data = st.secrets["GOOGLE_OAUTH_CLIENT"]["web"]
    elif "web" in st.secrets:
        secrets_data = st.secrets["web"]

    if secrets_data:
        try:
            # We reconstruct the client config dictionary expected by the google_auth library
            client_config = {"web": {
                "client_id": secrets_data["client_id"],
                "project_id": secrets_data["project_id"],
                "auth_uri": secrets_data["auth_uri"],
                "token_uri": secrets_data["token_uri"],
                "auth_provider_x509_cert_url": secrets_data["auth_provider_x509_cert_url"],
                "client_secret": secrets_data["client_secret"],
                # We enforce our specific Redirect URI to prevent mismatch errors
                "redirect_uris": [REDIRECT_URI],
            }}
            
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
        except Exception as e:
            st.error(f"Error reading secrets: {e}")
            return None

    # Strategy B: Fallback to local file (Development)
    # If no secrets are found, we look for a 'client_secret.json' file.
    elif os.path.exists('client_secret.json'):
        try:
            flow = Flow.from_client_secrets_file(
                'client_secret.json',
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None
    
    if not flow:
        st.error("⚠️ No configuration found. Please check secrets or client_secret.json.")
        return None

    # 3. Handle the Callback (User returns from Google)
    # We check if the URL contains an authorization 'code'.
    auth_code = st.query_params.get("code")
    
    if auth_code:
        try:
            # Exchange the auth code for an access token
            flow.fetch_token(code=auth_code)
            
            # Save the credentials in the session state to keep the user logged in
            st.session_state.credentials = flow.credentials
            
            # Clear the URL parameters (remove the code) and reload the app
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.warning("⚠️ Login failed.")
            st.caption(f"Reason: {e}")
            if st.button("🔄 Try again"):
                st.query_params.clear()
                st.rerun()
            return None
    else:
        # If not logged in and no code is present, generate the Google Login URL
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
