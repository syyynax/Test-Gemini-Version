import streamlit as st
import database
import auth
import google_service
import recommender
from streamlit_calendar import calendar
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="HSG Planner", layout="wide")
database.init_db()

# --- SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home & Profil", "Activity Planner", "Gruppen-Kalender"])

# --- SEITE 1: PROFIL ---
if page == "Home & Profil":
    st.title("👤 User Profil & Setup")
    st.write("Erstelle hier Profile für dich und deine Freunde.")
    
    # clear_on_submit=True sorgt dafür, dass die Felder nach dem Speichern leer werden
    with st.form("profile_form", clear_on_submit=True):
        st.info("💡 Tipp: Nutze unterschiedliche E-Mails für unterschiedliche Personen.")
        # Markierung als Pflichtfeld im Label
        name = st.text_input("Dein Name *")
        email = st.text_input("Email (dient als ID) *")
        
        st.write("Deine Interessen:")
        c1, c2, c3 = st.columns(3)
        prefs = []
        if c1.checkbox("Sport"): prefs.append("Sport")
        if c2.checkbox("Kultur"): prefs.append("Kultur")
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Essen"): prefs.append("Essen")
        if c2.checkbox("Lernen"): prefs.append("Education")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        submitted = st.form_submit_button("Profil Speichern")
        
        if submitted:
            # --- VALIDIERUNG: Sind die Pflichtfelder da? ---
            if not name.strip():
                st.error("❌ Bitte gib einen Namen ein.")
            elif not email.strip():
                st.error("❌ Bitte gib eine E-Mail-Adresse ein.")
            else:
                # Alles ok -> Speichern
                success, operation = database.add_user(name, email, prefs)
                if success:
                    if operation == "updated":
                        st.success(f"Profil von {name} wurde aktualisiert!")
                    else:
                        st.success(f"Neues Profil für {name} erstellt!")
                else: 
                    st.error(f"Fehler: {operation}")

    st.divider()
    st.subheader("Aktuelle User in der Datenbank")
    users = database.get_all_users()
    if not users:
        st.warning("Noch keine User angelegt.")
    else:
        for u in users:
            st.text(f"• {u[0]} (Interessen: {u[1]})")


# --- SEITE 2: PLANNER ---
elif page == "Activity Planner":
    st.title("📅 Smart Group Planner")
    
    auth_result = auth.get_google_service()
    user_busy_map = {} 
    
    if isinstance(auth_result, str):
        st.warning("Nicht verbunden.")
        st.link_button("Mit Google Kalender verbinden", auth_result)
    elif auth_result:
        service = auth_result
        st.success("✅ Verbunden!")
        
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        # Events holen
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        with st.expander("🔍 Diagnose: Termine", expanded=False):
            st.write(f"Google hat {stats['total_events']} Termine gefunden.")
            if stats['unassigned_titles']:
                st.write(f"Ignoriert: {stats['unassigned_titles']}")

    st.divider()

    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Bitte erst Profile anlegen.")
    else:
        user_names = [u[0] for u in all_users_data]
        selected = st.multiselect("Wer soll geplant werden?", user_names, default=user_names)
        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        # --- FIX: Session State initialisieren ---
        if 'ranked_results' not in st.session_state:
            st.session_state.ranked_results = None

        # Wenn Button geklickt wird -> Berechnen und in Session State SPEICHERN
        if st.button("🚀 Analyse Starten") and selected:
            events_df = recommender.load_local_events("events.csv") 
            if events_df.empty:
                 events_df = recommender.load_local_events("events.xlsx")

            # Ergebnis merken!
            st.session_state.ranked_results = recommender.find_best_slots_for_group(
                events_df, 
                user_busy_map, 
                selected, 
                user_prefs_dict,
                min_attendees=2
            )

        # --- ANZEIGE: Immer das anzeigen, was im Speicher ist ---
        if st.session_state.ranked_results is not None:
            ranked_df = st.session_state.ranked_results
            
            if not ranked_df.empty:
                st.subheader("🎯 Top Vorschläge")
                
                # Option zum Zurücksetzen
                if st.button("Ergebnisse löschen"):
                    st.session_state.ranked_results = None
                    st.rerun()

                for idx, row in ranked_df.head(5).iterrows():
                    match_percent = int(row['match_score'] * 100)
                    with st.expander(f"{row['Title']} ({row['attendee_count']} Pers.) - {match_percent}% Match", expanded=True):
                        st.write(f"📅 {row['Start'].strftime('%d.%m. %H:%M')} | {row['Category']}")
                        st.write(f"Dabei: {row['attendees']}")
                        st.progress(match_percent / 100)
                
                cal_events = []
                for _, row in ranked_df.iterrows():
                    cal_events.append({
                        "title": row['Title'],
                        "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                        "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                        "backgroundColor": "#28a745"
                    })
                calendar(events=cal_events, options={"initialView": "listWeek", "height": 400})
            else:
                st.warning("Keine passenden Termine gefunden.")

# --- SEITE 3: GRUPPEN KALENDER ---
elif page == "Gruppen-Kalender":
    st.title("🗓️ Gruppen-Kalender Übersicht")
    auth_result = auth.get_google_service()
    if auth_result and not isinstance(auth_result, str):
        service = auth_result
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        cal_events = []
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        
        for i, (user_name, events) in enumerate(user_busy_map.items()):
            color = colors[i % len(colors)]
            for event in events:
                cal_events.append({
                    "title": f"{user_name}: {event.get('summary', 'Termin')}",
                    "start": event['start'].isoformat(),
                    "end": event['end'].isoformat(),
                    "backgroundColor": color,
                    "borderColor": color
                })
        
        if cal_events:
            calendar(events=cal_events, options={"initialView": "dayGridMonth", "height": 700})
        else:
            st.info("Keine Termine gefunden.")
    else:
        st.warning("Bitte erst verbinden.")
