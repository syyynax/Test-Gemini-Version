import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Konfiguration
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
# WICHTIG: Diese URL muss exakt so in der Google Cloud Console stehen
REDIRECT_URI = "https://projectrepo-nelb9xkappkqy6bhbwcmqwp.streamlit.app"

def get_google_service():
    """
    Handled den gesamten Login-Flow.
    """
    if "credentials" not in st.session_state:
        st.session_state.credentials = None

    # Fall 1: Bereits eingeloggt
    if st.session_state.credentials:
        return build("calendar", "v3", credentials=st.session_state.credentials)

    # Fall 2: Login starten oder Code verarbeiten
    if os.path.exists('client_secret.json'):
        try:
            flow = Flow.from_client_secrets_file(
                'client_secret.json',
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
            # Sicherheitsnetz: Redirect URI explizit setzen
            flow.redirect_uri = REDIRECT_URI
            
        except Exception as e:
            st.error(f"Fehler beim Laden von client_secret.json: {e}")
            return None
        
        # Wurde der User gerade von Google zurückgeleitet? (Code in URL)
        if st.query_params.get("code"):
            code = st.query_params.get("code")
            try:
                flow.fetch_token(code=code)
                st.session_state.credentials = flow.credentials
                # URL bereinigen und neu laden
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                # Detaillierte Fehlermeldung für Debugging
                st.error("Login fehlgeschlagen (UnauthorizedClientError).")
                st.warning("Diagnose:")
                st.write(f"1. Der Code sendet diese Redirect-URL: `{REDIRECT_URI}`")
                st.write("2. Bitte prüfen Sie in der Google Cloud Console, ob diese URL exakt so unter 'Autorisierte Weiterleitungs-URIs' steht.")
                st.write("3. Fügen Sie in der Cloud Console zur Sicherheit auch die Variante mit '/' am Ende hinzu.")
                st.code(f"Fehler-Details: {e}")
                
                # Button zum Bereinigen der URL
                if st.button("Zurück zum Start (URL bereinigen)"):
                    st.query_params.clear()
                    st.rerun()
                return None
            
        else:
            # Generiere Login-Link
            auth_url, _ = flow.authorization_url(prompt='consent')
            return auth_url
    else:
        st.error("⚠️ Datei 'client_secret.json' fehlt im Repository.")
        return None
