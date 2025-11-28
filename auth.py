import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Konfiguration
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
# WICHTIG: Ändert dies auf eure deployed URL, wenn ihr online geht
REDIRECT_URI = "https://projectrepo-nelb9xkappkqy6bhbwcmqwp.streamlit.app"

def get_google_service():
    """
    Handled den gesamten Login-Flow.
    Gibt entweder das 'service' Objekt zurück (wenn eingeloggt),
    oder einen Auth-Link (String),
    oder None (wenn Fehler).
    """
    if "credentials" not in st.session_state:
        st.session_state.credentials = None

    # Fall 1: Bereits eingeloggt
    if st.session_state.credentials:
        return build("calendar", "v3", credentials=st.session_state.credentials)

    # Fall 2: Login starten oder Code verarbeiten
    if os.path.exists('client_secret.json'):
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Wurde der User gerade von Google zurückgeleitet? (Code in URL)
        if st.query_params.get("code"):
            code = st.query_params.get("code")
            flow.fetch_token(code=code)
            st.session_state.credentials = flow.credentials
            
            # URL bereinigen, damit der Code nicht dort stehen bleibt
            st.query_params.clear()
            st.rerun()
            
        else:
            # Generiere Login-Link
            auth_url, _ = flow.authorization_url(prompt='consent')
            return auth_url
    else:
        return None
