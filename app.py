import streamlit as st
import database
import auth
import google_service
import recommender
from streamlit_calendar import calendar
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="HSG Planner V2 (NEU)", layout="wide")
database.init_db()

# --- SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home & Profil", "Activity Planner", "Gruppen-Kalender"])

# --- SEITE 1: PROFIL ---
if page == "Home & Profil":
    st.title("👤 User Profil & Setup")
    
    with st.form("profile_form"):
        st.info("💡 Tipp: Dein Name muss im Titel deiner Google Kalender Termine vorkommen (z.B. 'Max: Zahnarzt'), damit die App sie zuordnen kann.")
        name = st.text_input("Dein Name")
        email = st.text_input("Email")
        
        st.write("Deine Interessen:")
        c1, c2, c3 = st.columns(3)
        prefs = []
        if c1.checkbox("Sport"): prefs.append("Sport")
        if c2.checkbox("Kultur"): prefs.append("Kultur")
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Essen"): prefs.append("Essen")
        if c2.checkbox("Lernen"): prefs.append("Education")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        if st.form_submit_button("Profil Speichern"):
            if database.add_user(name, email, prefs):
                st.success(f"Profil für {name} gespeichert!")
            else: 
                st.error("Fehler beim Speichern.")

    st.divider()
    st.subheader("Aktuelle User in der Datenbank")
    for u in database.get_all_users():
        st.text(f"• {u[0]} (Interessen: {u[1]})")


# --- SEITE 2: PLANNER ---
elif page == "Activity Planner":
    st.title("📅 Smart Group Planner")
    
    # Login über auth.py
    auth_result = auth.get_google_service()
    
    user_busy_map = {} 
    
    if isinstance(auth_result, str):
        st.warning("Nicht verbunden.")
        st.link_button("Mit Google Kalender verbinden", auth_result)
    elif auth_result:
        service = auth_result
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        # Events laden
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        st.success(f"✅ Verbunden! {stats['total_events']} Termine geladen.")
        if stats['unassigned'] > 0:
            st.caption(f"ℹ️ {stats['unassigned']} Termine ignoriert (Kein User-Name im Titel gefunden).")
    
    # Kein else-Block nötig, Fehler werden in auth.py behandelt

    st.divider()

    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Bitte erst Profile auf der Home-Seite anlegen.")
    else:
        user_names = [u[0] for u in all_users_data]
        selected = st.multiselect("Wer soll geplant werden?", user_names, default=user_names)
        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        if st.button("🚀 Analyse Starten") and selected:
            events_df = recommender.load_local_events()
            
            ranked_df = recommender.find_best_slots_for_group(
                events_df, 
                user_busy_map, 
                selected, 
                user_prefs_dict,
                min_attendees=2
            )
            
            if not ranked_df.empty:
                st.subheader("🎯 Top Vorschläge")
                
                for idx, row in ranked_df.head(5).iterrows():
                    match_percent = int(row['match_score'] * 100)
                    count = row['attendee_count']
                    total = len(selected)
                    
                    with st.expander(f"{row['Title']} ({count}/{total} Personen) - {match_percent}% Match", expanded=True):
                        c1, c2 = st.columns([1, 2])
                        c1.write(f"📅 **{row['Start'].strftime('%d.%m. %H:%M')}**")
                        c1.caption(row['Category'])
                        c2.write(f"**Dabei:** {row['attendees']}")
                        c2.progress(match_percent / 100, f"Match: {match_percent}%")
                        c2.write(f"_{row['Description']}_")

                st.subheader("Kalender Übersicht der Vorschläge")
                cal_events = []
                for _, row in ranked_df.iterrows():
                    cal_events.append({
                        "title": f"{row['Title']} ({row['attendee_count']} Pers.)",
                        "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                        "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                        "backgroundColor": "#28a745" if row['attendee_count'] == len(selected) else "#ffc107",
                        "borderColor": "white"
                    })
                calendar(events=cal_events, options={"initialView": "listWeek", "height": 400})

            else:
                st.warning("Keine Termine gefunden, an denen mindestens 2 Personen Zeit haben.")

# --- SEITE 3: GRUPPEN KALENDER ---
elif page == "Gruppen-Kalender":
    st.title("🗓️ Gruppen-Kalender Übersicht")
    st.write("Hier seht ihr alle Termine aller Freunde in einer Übersicht.")
    
    auth_result = auth.get_google_service()
    
    if auth_result and not isinstance(auth_result, str):
        service = auth_result
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        cal_events = []
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#F7DC6F", "#BB8FCE", "#D2B4DE"]
        
        for i, (user_name, events) in enumerate(user_busy_map.items()):
            color = colors[i % len(colors)]
            
            for event in events:
                cal_events.append({
                    "title": f"{user_name}: {event.get('summary', 'Termin')}",
                    "start": event['start'].isoformat(),
                    "end": event['end'].isoformat(),
                    "backgroundColor": color,
                    "borderColor": color,
                    "allDay": False
                })
        
        if cal_events:
            calendar(events=cal_events, options={
                "initialView": "dayGridMonth",
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,listWeek"
                },
                "height": 700
            })
            
            st.write("Legende:")
            cols = st.columns(len(user_busy_map))
            for i, user_name in enumerate(user_busy_map.keys()):
                color = colors[i % len(colors)]
                cols[i].markdown(f":{color}[**{user_name}**]")
                
        else:
            st.info("Keine Termine gefunden.")
            
    else:
        st.warning("Bitte gehe zuerst zum 'Activity Planner' und verbinde dich mit Google.")
