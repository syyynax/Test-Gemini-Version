import streamlit as st
import pandas as pd  # WICHTIG: Pandas importieren!
import database
import auth
import google_service
import recommender
import visualization
from streamlit_calendar import calendar
from datetime import datetime, timedelta

# --- SETUP ---
st.set_page_config(page_title="Meetly", page_icon="👋", layout="wide")
database.init_db()

# --- SESSION STATE INITIALISIERUNG ---
# Wir brauchen einen Speicher für die ausgewählten Events
if 'selected_events' not in st.session_state:
    st.session_state.selected_events = []

# --- SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Start", "Profiles", "Activity Planner", "Group Calendar"])

# --- PAGE 0: START PAGE ---
if page == "Start":
    st.markdown("<h1 style='text-align: center;'>✨ Welcome to Meetly!</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>The App to finally bring your friends together.</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### How it works:
        1. **👤 Create Profile** Go to *Profiles* and register yourself.
        2. **📅 Connect Calendar** Link your Google Calendar in the *Activity Planner*.
        3. **🚀 Plan** Let Meetly find the perfect time slots and activities for your group!
        """)
    with col2:
        st.info("👈 Select 'Profiles' in the menu on the left to get started!")

# --- PAGE 1: PROFILES ---
elif page == "Profiles":
    st.title("👤 User Profile & Setup")
    st.write("Create profiles for you and your friends here.")
    
    with st.form("profile_form", clear_on_submit=True):
        st.info("💡 Tip: Use different emails for different people.")
        name = st.text_input("Your Name *")
        email = st.text_input("Email (serves as ID) *")
        
        st.write("Your Interests:")
        c1, c2, c3 = st.columns(3)
        prefs = []
        if c1.checkbox("Sport"): prefs.append("Sport")
        if c2.checkbox("Culture"): prefs.append("Kultur")
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Food"): prefs.append("Essen")
        if c2.checkbox("Education"): prefs.append("Education")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            if not name.strip():
                st.error("❌ Please enter a name.")
            elif not email.strip():
                st.error("❌ Please enter an email address.")
            else:
                success, operation = database.add_user(name, email, prefs)
                if success:
                    if operation == "updated":
                        st.success(f"Profile for {name} updated!")
                    else:
                        st.success(f"New profile created for {name}!")
                else: 
                    st.error(f"Error: {operation}")

    st.divider()
    st.subheader("Current Users in Database")
    users = database.get_all_users()
    if not users:
        st.warning("No users created yet.")
    else:
        for u in users:
            st.text(f"• {u[0]} (Interests: {u[1]})")

# --- PAGE 2: ACTIVITY PLANNER ---
elif page == "Activity Planner":
    st.title("📅 Smart Group Planner")
    
    auth_result = auth.get_google_service()
    user_busy_map = {} 
    
    if isinstance(auth_result, str):
        st.warning("Not connected.")
        st.link_button("Connect with Google Calendar", auth_result)
    elif auth_result:
        service = auth_result
        st.success("✅ Connected!")
        
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        # Fetch Events
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        with st.expander("🔍 Diagnostic: Google Calendar Events", expanded=False):
            st.write(f"Google found {stats.get('total_events', 0)} events.")
            if stats.get('unassigned_titles'):
                st.write(f"Ignored: {stats['unassigned_titles']}")

    st.divider()

    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Please create profiles first.")
    else:
        # Hier ist die neue Datumsauswahl!
        today = datetime.now().date()
        
        col1, col2 = st.columns(2)
        with col1:
            user_names = [u[0] for u in all_users_data]
            selected = st.multiselect("Who is planning?", user_names, default=user_names)
        
        with col2:
            # Wähle ein Datum, wir berechnen die Woche darum herum
            selected_date = st.date_input("Plan for which week?", value=today)
            
            # Berechne Montag (Start) und Sonntag (Ende) der ausgewählten Woche
            start_of_week = selected_date - timedelta(days=selected_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            st.caption(f"📅 Showing events for: **{start_of_week.strftime('%d.%m.%Y')} - {end_of_week.strftime('%d.%m.%Y')}**")

        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        # Session State
        if 'ranked_results' not in st.session_state:
            st.session_state.ranked_results = None

        if st.button("🚀 Start Analysis") and selected:
            # 1. Alle Events laden (30 Tage)
            events_df = recommender.load_local_events("events.csv") 
            if events_df.empty:
                 events_df = recommender.load_local_events("events.xlsx")
            
            # 2. FILTERN: Nur Events der ausgewählten Woche behalten
            if not events_df.empty:
                # Sicherstellen, dass 'Start' ein Datetime-Objekt ist
                events_df['Start'] = pd.to_datetime(events_df['Start'])
                
                # Filter anwenden
                mask = (events_df['Start'].dt.date >= start_of_week) & (events_df['Start'].dt.date <= end_of_week)
                events_df_filtered = events_df.loc[mask].copy()
            else:
                events_df_filtered = events_df

            # 3. Nur die gefilterten Events an den Recommender geben
            st.session_state.ranked_results = recommender.find_best_slots_for_group(
                events_df_filtered, 
                user_busy_map, 
                selected, 
                user_prefs_dict,
                min_attendees=1 
            )

        if st.session_state.ranked_results is not None:
            ranked_df = st.session_state.ranked_results
            
            if not ranked_df.empty:
                st.subheader("🎯 Top Suggestions")
                if st.button("Clear Results"):
                    st.session_state.ranked_results = None
                    st.rerun()
                
                st.markdown("---")
                
                total_group_size = len(selected)

                for idx, row in ranked_df.head(10).iterrows():
                    # Werte sicher abrufen
                    interest_score = row.get('final_interest_score', 0)
                    avail_score = row.get('availability_score', 0)
                    
                    is_avail_perfect = (avail_score >= 0.99)
                    is_interest_high = (interest_score > 0.6)
                    is_interest_perfect = (interest_score >= 0.99)
                    
                    time_str = f"{row['Start'].strftime('%A, %H:%M')} - {row['End'].strftime('%H:%M')}"

                    attending_count = row['attendee_count']
                    missing_people = []
                    if not is_avail_perfect:
                        attending_list = [x.strip() for x in row['attendees'].split(',')]
                        missing_people = [p for p in selected if p not in attending_list]

                    # 1. THE JACKPOT (Gold)
                    if is_avail_perfect and is_interest_perfect:
                        with st.container(border=True):
                            st.markdown(f"### 🏆 **PERFECT MATCH: {row['Title']}**")
                            st.info("✨ Everyone is free AND it matches everyone's interests perfectly!")
                            
                            c1, c2, c3 = st.columns([1, 2, 1])
                            c1.write(f"📅 **{time_str}**")
                            c1.caption(f"Category: {row['Category']}")
                            c2.write(f"**Interests Matched:** {row['matched_tags']}")
                            
                            sc1, sc2 = c3.columns(2)
                            with sc1:
                                st.write(f"💙 **Interest**")
                                st.write(f"**{int(interest_score*100)}%**")
                            with sc2:
                                st.write(f"🕒 **Avail.**")
                                st.write(f"**{int(avail_score*100)}%**")
                            
                            # ADD BUTTON
                            if st.button(f"Add '{row['Title']}' to Calendar", key=f"btn_{idx}"):
                                new_event = {
                                    "title": f"🎉 {row['Title']}",
                                    "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "backgroundColor": "#FFD700", # Gold
                                    "borderColor": "#FFD700"
                                }
                                st.session_state.selected_events.append(new_event)
                                st.toast(f"Added {row['Title']} to Group Calendar!")
                    
                    # 2. TIME PERFECT (Grün)
                    elif is_avail_perfect:
                        with st.container(border=True):
                            st.markdown(f"### ✅ **GOOD TIMING: {row['Title']}**")
                            st.success("🕒 Everyone is free at this time.")
                            
                            c1, c2, c3 = st.columns([1, 2, 1])
                            c1.write(f"📅 **{time_str}**")
                            c2.write(f"**Interests Matched:** {row['matched_tags']}")
                            if interest_score < 0.3:
                                c2.caption("Low interest match, but timing works!")
                            
                            sc1, sc2 = c3.columns(2)
                            with sc1:
                                st.write(f"💙 **Interest**")
                                st.write(f"**{int(interest_score*100)}%**")
                            with sc2:
                                st.write(f"🕒 **Avail.**")
                                st.write(f"**{int(avail_score*100)}%**")
                            
                            # ADD BUTTON
                            if st.button(f"Add '{row['Title']}' to Calendar", key=f"btn_{idx}"):
                                new_event = {
                                    "title": f"✅ {row['Title']}",
                                    "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "backgroundColor": "#28a745", # Grün
                                    "borderColor": "#28a745"
                                }
                                st.session_state.selected_events.append(new_event)
                                st.toast(f"Added {row['Title']} to Group Calendar!")

                    # 3. INTEREST PERFECT (Blau)
                    elif is_interest_high:
                        with st.container(border=True):
                            st.markdown(f"### 💙 **HIGH INTEREST: {row['Title']}**")
                            st.warning(f"⚠️ Only {attending_count}/{total_group_size} people are free, but they will love it!")
                            
                            c1, c2, c3 = st.columns([1, 2, 1])
                            c1.write(f"📅 **{time_str}**")
                            c2.write(f"**Who can go:** {row['attendees']}")
                            if missing_people:
                                c2.caption(f"Busy: {', '.join(missing_people)}")
                            
                            sc1, sc2 = c3.columns(2)
                            with sc1:
                                st.write(f"💙 **Interest**")
                                st.write(f"**{int(interest_score*100)}%**")
                            with sc2:
                                st.write(f"🕒 **Avail.**")
                                st.write(f"**{int(avail_score*100)}%**")
                            
                            # ADD BUTTON
                            if st.button(f"Add '{row['Title']}' to Calendar", key=f"btn_{idx}"):
                                new_event = {
                                    "title": f"💙 {row['Title']}",
                                    "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "backgroundColor": "#1E90FF", # Blau
                                    "borderColor": "#1E90FF"
                                }
                                st.session_state.selected_events.append(new_event)
                                st.toast(f"Added {row['Title']} to Group Calendar!")

                    # 4. NORMAL
                    else:
                        with st.expander(f"{row['Title']} ({attending_count}/{total_group_size} Ppl)"):
                            c1, c2, c3 = st.columns([1, 1, 1]) 
                            c1.write(f"📅 **{time_str}**")
                            c1.caption(f"Category: {row['Category']}")
                            c2.write(f"**Attendees:** {row['attendees']}")
                            if missing_people:
                                c2.caption(f"❌ Missing: {', '.join(missing_people)}")
                            
                            sc1, sc2 = c3.columns(2)
                            with sc1:
                                st.write(f"💙 **Interest**")
                                st.write(f"**{int(interest_score*100)}%**")
                            with sc2:
                                st.write(f"🕒 **Avail.**")
                                st.write(f"**{int(avail_score*100)}%**")
                            
                            st.write("**Why this option?**")
                            if attending_count > 1:
                                st.info(f"It works for {attending_count} people.")
                            elif row['matched_tags'] != "General":
                                st.info(f"It matches interest: '{row['matched_tags']}'")
                            else:
                                st.write("It's an available option to consider.")
                                
                            if row['Description']:
                                st.write(f"_{row['Description']}_")
                            
                            # ADD BUTTON (Auch hier!)
                            if st.button(f"Add to Calendar", key=f"btn_{idx}"):
                                new_event = {
                                    "title": f"📌 {row['Title']}",
                                    "start": row['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "end": row['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                                    "backgroundColor": "#6c757d", # Grau
                                    "borderColor": "#6c757d"
                                }
                                st.session_state.selected_events.append(new_event)
                                st.toast(f"Added {row['Title']} to Group Calendar!")
            else:
                st.warning("No suitable events found.")

# --- PAGE 3: GROUP CALENDAR ---
elif page == "Group Calendar":
    st.title("🗓️ Group Calendar Overview")
    auth_result = auth.get_google_service()
    if auth_result and not isinstance(auth_result, str):
        service = auth_result
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        cal_events = []
        visualization_data = [] 
        
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        
        # 1. Normale Termine der User
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
                
                visualization_data.append({
                    "summary": event.get('summary', 'Termin'),
                    "start": event['start'],
                    "end": event['end'],
                    "person": user_name 
                })
        
        # 2. HIER: Die ausgewählten Events aus dem Activity Planner hinzufügen!
        if st.session_state.selected_events:
            cal_events.extend(st.session_state.selected_events)
            st.success(f"Showing {len(st.session_state.selected_events)} selected group activities!")
            
            if st.button("Clear selected activities"):
                st.session_state.selected_events = []
                st.rerun()
        
        if cal_events:
            calendar(events=cal_events, options={"initialView": "dayGridMonth", "height": 700})
            st.markdown("---")
            visualization.show_visualizations(visualization_data)
        else:
            st.info("No events found.")
    else:
        st.warning("Please connect first in the 'Activity Planner'.")
