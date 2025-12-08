import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar

# Import your modules
import database
import auth
import google_service
import recommender
import visualization

def show_start_page():
    """
    Renders the Start Page with a welcome message and a short guide.
    This serves as the initial landing page for the application. 
    """
    st.markdown("<h1 style='text-align: center;'>✨ Welcome to Meetly! ✨</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>The App to finally bring your friends together.</h3>", unsafe_allow_html=True)
    st.markdown("---")

    # Use columns to present the information clearly 
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### How it works:
        1. **Create Profile** Go to *Profiles* and register yourself.
        2. **Connect Calendar** Link your Google Calendar in the *Activity Planner*.
        3. **Plan** Let Meetly find the perfect time slots and activities for your group!
        """)
    with col2:
        st.info("Select 'Profiles' in the menu on the left to get started!")

def show_profiles_page():
    """
    Renders the Profile setup page where users can register and set or update preferences.
    """
    st.title("👤 User Profile & Setup")
    st.write("Create profiles for you and your friends here.")
    # Use st.form for grouping input widgets and ensuring single submission 
    with st.form("profile_form", clear_on_submit=True):
        st.info("Use different emails for different people.")
        name = st.text_input("Your Name *")
        email = st.text_input("Email (serves as ID) *")
        
        st.write("Your Interests:")
        # Use columns for a compact display of interest checkboxes 
        c1, c2, c3 = st.columns(3)
        prefs = []
        if c1.checkbox("Sport"): prefs.append("Sport")
        if c2.checkbox("Culture"): prefs.append("Culture")
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Food"): prefs.append("Food")
        if c2.checkbox("Music"): prefs.append("Music")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            # Simple form validation 
            if not name.strip():
                st.error("❌ Please enter a name.")
            elif not email.strip():
                st.error("❌ Please enter an email address.")
            else:
                # Call the database module to save or update user data 
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
    # Fetch and display all current users for transparency 
    users = database.get_all_users()
    if not users:
        st.warning("No users created yet.")
    else:
        for u in users:
            st.text(f"• {u[0]} (Interests: {u[1]})")

def render_card_content(row, time_str, location, interest_score, avail_score, missing_people, idx, save_callback, color, is_expander=False):
    """
    Helper function to render the detailed content for a single recommended event card.
    
    """
    # Use columns to align content neatly 
    c1, c2, c3 = st.columns([1, 2, 1.5])
    
    # Column 1: Time & Location & Catergory 
    c1.write(f" **{time_str}**")
    c1.write(f"📍 **{location}**") 
    c1.caption(f"Category: {row['Category']}")
    
    # Column 2: Interests and Missing People 
    c2.write(f"**Interests Matched:** {row['matched_tags']}")
    if missing_people:
        c2.caption(f"❌ Missing: {', '.join(missing_people)}")
    
    # Column 3: The Scores (Side-by-Side)
    sc1, sc2 = c3.columns(2)
    with sc1:
        st.write(f" **Interest**")
        # Display score as the percentage 
        st.write(f"**{int(interest_score*100)}%**")
    with sc2:
        st.write(f" **Availability**")
        st.write(f"**{int(avail_score*100)}%**")
    
    # Extra explanation text for the 'Normal' (Grey) category 
    if is_expander:
        st.write("**Why this option?**")
        if row['attendee_count'] > 1:
            st.info(f"It works for {row['attendee_count']} people.")
        elif row['matched_tags'] != "General":
            st.info(f"It matches interest: '{row['matched_tags']}'")
        else:
            st.write("It's an available option to consider.")
        # Display the event description if present 
        if row['Description']:
            st.write(f"_{row['Description']}_")

    # The "Add to Calendar" button, keyed uniquely by event index 
    if st.button(f"Add '{row['Title']}' to Calendar", key=f"btn_{idx}"):
        save_callback(row, color, interest_score, location)
        
def show_activity_planner():
    """
    Renders the main planning interface.
    Here users connect their calendar, select participants, set the date range and view recommandations.
    """
    st.title("Smart Group Planner")
    # Initialize session state for limiting results 
    if 'results_limit' not in st.session_state:
        st.session_state.results_limit = 10
    
    # 1. Authentication Check & Connection
    auth_result = auth.get_google_service()
    user_busy_map = {}  # Dictionnary to store fetched events mapped to users 
    
    if isinstance(auth_result, str):
        # Authentication not complete (auth-result is the URL to connect)
        st.warning("Not connected.")
        st.markdown(f'<a href="{auth_result}" target="_self">🔗 Connect with Google Calendar</a>', unsafe_allow_html=True)
    elif auth_result:
        # Authentification successful (auth-result is the service objects)
        service = auth_result
        st.success("✅ Connected!")
        
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]
        
        # 2. Fetch Calendar Data
        # This calls the Google API to get all selected users events 
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        # Diagnostic box to help users debug why events might be missing
        with st.expander(" Diagnostic: Google Calendar Events", expanded=False):
            st.write(f"Google found {stats.get('total_events', 0)} events.")
            if stats.get('unassigned_titles'):
                st.write(f"Ignored: {stats['unassigned_titles']}")

    st.divider()

    # 3. Planning Setup (Participants & Date Range)
    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Please create profiles first.")
    else:
        today = datetime.now().date()
        
        # Layout: User selection on left, Week selection on right
        col1, col2 = st.columns(2)
        with col1:
            user_names = [u[0] for u in all_users_data]
            # Multi-select for choosing who is part of the planning group 
            selected = st.multiselect("Who is planning?", user_names, default=user_names)
        
        with col2:
            # Date input to select the target week
            selected_date = st.date_input("Plan for which week?", value=today)
            # Calculate the Monday and Sunday of the selected week 
            start_of_week = selected_date - timedelta(days=selected_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            st.caption(f"Showing events for: **{start_of_week.strftime('%d.%m.%Y')} - {end_of_week.strftime('%d.%m.%Y')}**")
        # Match user names to their interest preferences 
        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        # 4. Run Analysis Trigger 
        if st.button("Search Events") and selected:
            # Reset the display limit to 10 on a new search 
            st.session_state.results_limit = 10
            
            # Load local events database 
            events_df = recommender.load_local_events("events.csv") 
            # Fallback to load from (Excel file) XLSX if CVS fails 
            if events_df.empty:
                 events_df = recommender.load_local_events("events.xlsx")
            
            # Filter events to match the users selected week 
            if not events_df.empty:
                events_df['Start'] = pd.to_datetime(events_df['Start'])
                mask = (events_df['Start'].dt.date >= start_of_week) & (events_df['Start'].dt.date <= end_of_week)
                events_df_filtered = events_df.loc[mask].copy()
            else:
                events_df_filtered = events_df

            # Call the Recommender Engine to score potential events 
            st.session_state.ranked_results = recommender.find_best_slots_for_group(
                events_df_filtered, 
                user_busy_map, 
                selected, 
                user_prefs_dict,
                min_attendees=1 
            )

        # 5. Display Results
        if st.session_state.ranked_results is not None:
            ranked_df = st.session_state.ranked_results
            
            if not ranked_df.empty:
                st.subheader("🎯 Event Suggestions")
                # Button to clear the current results 
                if st.button("Clear Results"):
                    st.session_state.ranked_results = None
                    st.rerun()
                
                st.markdown("---")
                
                total_group_size = len(selected)

                # Apply the current result limit (for pagination)
                current_limit = st.session_state.results_limit
                visible_df = ranked_df.head(current_limit)

               # Iterate through results the top N results and render cards 
                for idx, row in visible_df.iterrows():
                    # Extract necessary scoring and location data 
                    interest_score = row.get('final_interest_score', 0)
                    avail_score = row.get('availability_score', 0)
                    location = row.get('location') # Use location from the dataframe 

                    # Determine categories for visual grouping/priority 
                    is_avail_perfect = (avail_score >= 0.99)
                    is_interest_high = (interest_score > 0.6)
                    is_interest_perfect = (interest_score >= 0.99)
                    
                    # Format time nicely (e.g., "Mon 14:00 - 16:00")
                    time_str = f"{row['Start'].strftime('%A, %H:%M')} - {row['End'].strftime('%H:%M')}"

                    # Calculate missing people for the warning text 
                    attending_count = row['attendee_count']
                    missing_people = []
                    if not is_avail_perfect:
                        # assumes 'attendees' is a comma-separated string
                        attending_list = [x.strip() for x in row['attendees'].split(',')]
                        # Find who was selected but is not in the attendee list 
                        missing_people = [p for p in selected if p not in attending_list]

                    # Define the Callback Function that saves the chosen event to the database 
                    def save_to_db_callback(r, col, score, loc):
                        saved = database.add_saved_event(
                            f"{r['Title']}",
                            r['Start'].strftime("%Y-%m-%dT%H:%M:%S"), # ISO format for compatability 
                            r['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                            col, # color associated with the result category 
                            r['Category'],
                            r['attendees'],
                            float(score),
                            loc
                        )
                        if saved:
                            st.toast(f"Saved '{r['Title']}' permanently to Calendar!")
                        else:
                            st.toast(f"'{r['Title']}' is already saved.")

                    # --- Rendering based on Recommendation Quality (Gold, Green, Blue, Grey) ---
                    
                    # 1. THE JACKPOT (Gold) Perfect availability AND perfect interest match 
                    if is_avail_perfect and is_interest_perfect:
                        with st.container(border=True):
                            st.markdown(f"### 🏆 **PERFECT MATCH: {row['Title']}**")
                            st.info("Everyone is free AND it matches everyone's interests perfectly!")
                            render_card_content(row, time_str, location, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#FFD700")
                    
                    # 2. TIME PERFECT (Green) - perfect availability 
                    elif is_avail_perfect:
                        with st.container(border=True):
                            st.markdown(f"### ✅ **GOOD TIMING: {row['Title']}**")
                            st.success(" Everyone is free at this time.")
                            render_card_content(row, time_str, location, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#28a745")

                    # 3. INTEREST PERFECT (Blue) - High interest match, but some people are busy
                    elif is_interest_high:
                        with st.container(border=True):
                            st.markdown(f"### 💙 **HIGH INTEREST: {row['Title']}**")
                            st.warning(f" Only {attending_count}/{total_group_size} people are free, but they will love it!")
                            render_card_content(row, time_str, location, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#1E90FF")

                    # 4. NORMAL (Grey) - Everything else 
                    else:
                        with st.expander(f"{row['Title']} ({attending_count}/{total_group_size} Ppl)"):
                            render_card_content(row, time_str, location, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#6c757d", is_expander=True)
                

                # Check whether there are more results than currently displayed
                if len(ranked_df) > current_limit:
                    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                    with col_b2:
                        # 'Show more' button if there are more results 
                        if st.button("Show more events", type="primary", use_container_width=True):
                            st.session_state.results_limit += 10 # increase limit by 10
                            st.rerun() # Return the script to display the new results

            else:
                st.warning("No suitable events found.")

def show_group_calendar():
    """
    Renders the visual calendar using streamlit-calender, it combines:
    Private Google Calender events (for busy slots)
    Saved group activities from the Meetly database (the planned events)
    Triggers visualization module to show usage statistics.
    """
    st.title("Group Calendar Overview")
    # Check for authentication again 
    auth_result = auth.get_google_service()
    if auth_result and not isinstance(auth_result, str):
        service = auth_result
        all_users_db = database.get_all_users()
        all_user_names = [u[0] for u in all_users_db]

        # Fetch private events from Google Calender 
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        cal_events = [] # List for full calender (streamlit-calender) events 
        visualization_data = [] # List for data required by the visualization module 
        # define a rotating colors for different user's private events 
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]
        
        # 1. Add Private Google Events
        for i, (user_name, events) in enumerate(user_busy_map.items()):
            color = colors[i % len(colors)]
            for event in events:
                # Format event for full calender/ streamlit-calender 
                cal_events.append({
                    "title": f"{user_name}: {event.get('summary', 'Termin')}",
                    "start": event['start'].isoformat(),
                    "end": event['end'].isoformat(),
                    "backgroundColor": color,
                    "borderColor": color,
                    # extended properties are used for the click handler 
                    "extendedProps": {"category": "Private", "attendees": user_name, "type": "google"}
                })
                
                # Collects data for the statistics visualizations
                visualization_data.append({
                    "summary": event.get('summary', 'Termin'),
                    "start": event['start'],
                    "end": event['end'],
                    "person": user_name 
                })
        
        # 2. Add Saved Group Events from Database
        saved_events = database.get_saved_events()
        if saved_events:
            cal_events.extend(saved_events)
            st.success(f"Loaded {len(saved_events)} saved group activities from Database!")

            # Option to clear all saved events from the database 
            if st.button("Clear ALL saved activities"):
                database.clear_saved_events()
                st.rerun()

        if cal_events:
            # Render Calendar with Click Callback
            calendar_return = calendar(
                events=cal_events, 
                options={"initialView": "dayGridMonth", "height": 700}, # display as month view initially 
                callbacks=["eventClick"] # Enable event click listener 
            )
            
            # Handle Clicks (Show event details popup)
            if calendar_return and "eventClick" in calendar_return:
                clicked_event = calendar_return["eventClick"]["event"]
                props = clicked_event.get("extendedProps", {})
                
                st.markdown("### Event Details")
                with st.container(border=True):
                    st.markdown(f"## {clicked_event['title']}")
                    
                    c1, c2 = st.columns(2)
                    
                    # Parse ISO time to readable format
                    raw_start = clicked_event.get('start', '')
                    raw_end = clicked_event.get('end', '')
                    try:
                        # Attempt to parse ISO format datetimes 
                        if "T" in raw_start:
                            s_dt = datetime.fromisoformat(raw_start)
                            e_dt = datetime.fromisoformat(raw_end)
                            if s_dt.date() == e_dt.date():
                                time_display = f"{s_dt.strftime('%A, %d.%m.')} | {s_dt.strftime('%H:%M')} - {e_dt.strftime('%H:%M')}"
                            else:
                                time_display = f"{s_dt.strftime('%a %H:%M')} - {e_dt.strftime('%a %H:%M')}"
                        else:
                            time_display = f"{raw_start} (All Day)"
                    except:
                        # Fallback for unexpected date formats 
                        time_display = f"{raw_start} - {raw_end}"
                    
                    c1.write(f" **Time:** {time_display}")
            
                    # Location display 
                    loc = props.get('location', '-')
                    if loc and loc != "TBD":
                         c1.write(f"📍 **Location:** {loc}")
                    
                    # Display extra info if available (Group Event) vs (Google Event)
                    if "category" in props and props.get("type") != "google":
                        # Details for events saved via the recommender 
                        c1.info(f"**Category:** {props.get('category', 'General')}")
                        c2.write(f"👥 **Attendees:** {props.get('attendees', 'Unknown')}")
                        score_val = props.get('match_score')
                        if score_val is not None:
                            c2.write(f" **Interest Score:** {int(float(score_val)*100)}%")
                    else:
                        # Details for private Google Calender events 
                        title = clicked_event['title']
                        if ":" in title:
                            person = title.split(":")[0]
                            c2.write(f"👤 **Person:** {person}")
                        else:
                            c2.write("👤 **Type:** Private Calendar Entry")
            
            st.markdown("---")
            # Render Charts based on the private events data
            # This shows the user who is busy and when 
            visualization.show_visualizations(visualization_data)
        else:
            st.info("No events found.")
    else:
        st.warning("Please connect first in the 'Activity Planner'.")
