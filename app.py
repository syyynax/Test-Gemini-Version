import streamlit as st
import database
import auth
import google_service
import recommender
import visualization  # IMPORT: Visualisierungsmodul
from streamlit_calendar import calendar
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="Meetly", page_icon="👋", layout="wide")
database.init_db()

# --- SIDEBAR ---
st.sidebar.title("Navigation")
# Page name updated to "Profiles" as requested
page = st.sidebar.radio("Go to", ["Start", "Profiles", "Activity Planner", "Group Calendar"])

# --- PAGE 0: START PAGE ---
if page == "Start":
    st.markdown("<h1 style='text-align: center;'>✨ Welcome to Meetly! ✨</h1>", unsafe_allow_html=True)
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
        if c2.checkbox("Culture"): prefs.append("Kultur") # DB values kept stable
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
        
        with st.expander("🔍 Diagnostic: Events", expanded=False):
            st.write(f"Google found {stats['total_events']} events.")
            if stats['unassigned_titles']:
                st.write(f"Ignored: {stats['unassigned_titles']}")

    st.divider()

    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Please create profiles first.")
    else:
        user_names = [u[0] for u in all_users_data]
        selected = st.multiselect("Who is planning?", user_names, default=user_names)
        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        # Session State for Results
        if 'ranked_results' not in st.session_state:
            st.session_state.ranked_results = None

        if st.button("🚀 Start Analysis") and selected:
            events_df = recommender.load_local_events("events.csv") 
            if events_df.empty:
                 events_df = recommender.load_local_events("events.xlsx")

            st.session_state.ranked_results = recommender.find_best_slots_for_group(
                events_df, 
                user_busy_map, 
                selected, 
                user_prefs_dict,
                min_attendees=2
            )

        if st.session_state.ranked_results is not None:
            ranked_df = st.session_state.ranked_results
            
            if not ranked_df.empty:
                st.subheader("🎯 Top Suggestions")
                if st.button("Clear Results"):
                    st.session_state.ranked_results = None
                    st.rerun()

                for idx, row in ranked_df.head(5).iterrows():
                    match_percent = int(row['match_score'] * 100)
                    with st.expander(f"{row['Title']} ({row['attendee_count']} Ppl.) - {match_percent}% Match", expanded=True):
                        st.write(f"📅 {row['Start'].strftime('%d.%m. %H:%M')} | {row['Category']}")
                        st.write(f"Attendees: {row['attendees']}")
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
        
        # Prepare lists for calendar AND visualization
        cal_events = []
        visualization_data = [] # List of dicts for visualization.py
        
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        
        for i, (user_name, events) in enumerate(user_busy_map.items()):
            color = colors[i % len(colors)]
            for event in events:
                # 1. Format for Calendar
                cal_events.append({
                    "title": f"{user_name}: {event.get('summary', 'Termin')}",
                    "start": event['start'].isoformat(),
                    "end": event['end'].isoformat(),
                    "backgroundColor": color,
                    "borderColor": color
                })
                
                # 2. Format for Visualization
                # We explicitly add the 'person' key so visualization.py doesn't have to guess
                visualization_data.append({
                    "summary": event.get('summary', 'Termin'),
                    "start": event['start'],
                    "end": event['end'],
                    "person": user_name 
                })
        
        if cal_events:
            # Show Calendar
            calendar(events=cal_events, options={"initialView": "dayGridMonth", "height": 700})
            
            st.markdown("---")
            
            # Show Visualization (New Feature)
            # This calls the function in visualization.py
            visualization.show_visualizations(visualization_data)
            
        else:
            st.info("No events found.")
    else:
        st.warning("Please connect first in the 'Activity Planner'.")
