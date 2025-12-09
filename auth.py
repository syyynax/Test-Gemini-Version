import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Allow OAuth over HTTP (necessary for localhost testing).
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Configuration: Request read-only access to the Google Calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# --- DYNAMIC REDIRECT URI ---
# 1. Get current environment ('production' or 'development') from secrets.
env_status = st.secrets.get("general", {}).get("environment", "development")

# 2. Set the correct Redirect URI based on environment to avoid mismatch errors.
if env_status == "production":
    REDIRECT_URI = "https://meetly-augzgdgermpiwnemrvgyuv.streamlit.app"
else:
    REDIRECT_URI = "http://localhost:8501"

def get_google_service():
    """
    Handles the entire OAuth2 login flow for Google Calendar API access.
    Flow is managed in three sequential steps:
    1. Check if the user is already authenticated in the current session
    2. Load client secrets (from Streamlit Secrets of local file) and initialize the OAuth flow. 
    3. Process the authorization code upon callback or generate the login URL.

    Returns:
        object/str/None: The Google Calendar API service object (if logged in), the authorization URL
        (if login is required), or None (on failure)
    """
    # 1. Check Session State
    # If the user is already logged in during this session, we don't need to authenticate again.
    # The application uses Streamlit's session state to store credentials, avoiding re-authentication
    # every time the app reruns 
    if "credentials" not in st.session_state:
        st.session_state.credentials = None

    # If valid credentials exist, build and return the API service immediately.
    if st.session_state.credentials:
        # Build and return the high-level API service object using the acquired credentials. 
        return build("calendar", "v3", credentials=st.session_state.credentials)

    # 2. Initialize Login Flow (Configuration Loading)
    flow = None
    
    # Strategy A: Load Secrets from Streamlit Cloud (Production Environment)
    secrets_data = None
    # Check common locations for the OAuth client configuration within Streamlit secrets
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
