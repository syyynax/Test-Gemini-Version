import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Konfiguration
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = "https://projectrepo-nelb9xkappkqy6bhbwcmqwp.streamlit.app"

def get_google_service():
    """
    Handled den Login-Flow. 
    Liest Secrets aus 'GOOGLE_OAUTH_CLIENT.web.*'
    """
    if "credentials" not in st.session_state:
        st.session_state.credentials = None

    # 1. Bereits eingeloggt?
    if st.session_state.credentials:
        return build("calendar", "v3", credentials=st.session_state.credentials)

    # 2. Login Flow starten
    flow = None
    
    # --- ANPASSUNG HIER: Wir suchen nach deinem speziellen Key ---
    secrets_data = None
    
    # Fall A: Deine Struktur (GOOGLE_OAUTH_CLIENT.web...)
    if "GOOGLE_OAUTH_CLIENT" in st.secrets and "web" in st.secrets["GOOGLE_OAUTH_CLIENT"]:
        secrets_data = st.secrets["GOOGLE_OAUTH_CLIENT"]["web"]
    
    # Fall B: Standard Struktur (direkt [web])
    elif "web" in st.secrets:
        secrets_data = st.secrets["web"]

    if secrets_data:
        try:
            # Wir bauen das Dictionary so nach, wie die Library es erwartet
            client_config = {"web": {
                "client_id": secrets_data["client_id"],
                "project_id": secrets_data["project_id"],
                "auth_uri": secrets_data["auth_uri"],
                "token_uri": secrets_data["token_uri"],
                "auth_provider_x509_cert_url": secrets_data["auth_provider_x509_cert_url"],
                "client_secret": secrets_data["client_secret"],
                "redirect_uris": secrets_data["redirect_uris"],
            }}
            
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
        except Exception as e:
            st.error(f"Fehler beim Lesen der Secrets: {e}")
            return None

    # OPTION C: Fallback auf Datei (falls lokal getestet wird)
    elif os.path.exists('client_secret.json'):
        try:
            flow = Flow.from_client_secrets_file(
                'client_secret.json',
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
        except Exception as e:
            st.error(f"Fehler beim Laden von client_secret.json: {e}")
            return None
    
    if not flow:
        st.error("⚠️ Keine Konfiguration gefunden.")
        st.info("Erwartet in Secrets: [GOOGLE_OAUTH_CLIENT.web] oder [web]")
        return None

    # 3. Auth Code verarbeiten
    auth_code = st.query_params.get("code")
    if auth_code:
        try:
            flow.fetch_token(code=auth_code)
            st.session_state.credentials = flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.warning("⚠️ Login-Sitzung abgelaufen.")
            if st.button("🔄 Neu versuchen"):
                st.query_params.clear()
                st.rerun()
            return None
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
