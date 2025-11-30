import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar

# Import our own modules
import database
import auth
import google_service
import recommender
import visualization

def show_start_page():
    """
    Renders the landing page of the application.
    
    Why: This serves as the entry point for users, explaining what the app does
    and guiding them on how to get started. It improves the user experience (UX).
    """
    # We use HTML inside markdown to center the text for better visual appeal.
    st.markdown("<h1 style='text-align: center;'>✨ Welcome to Meetly! ✨</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>The App to finally bring your friends together.</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    # We use columns to create a two-sided layout (Text on left, Info box on right).
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

def show_profiles_page():
    """
    Renders the user registration page.
    
    Why: We need to collect user preferences (interests) and identities (names/emails)
    to make personalized recommendations later.
    """
    st.title("👤 User Profile & Setup")
    st.write("Create profiles for you and your friends here.")
    
    # We use 'clear_on_submit=True' so the form resets after saving.
    # This allows users to quickly add multiple friends one after another.
    with st.form("profile_form", clear_on_submit=True):
        st.info("💡 Tip: Use different emails for different people.")
        
        # Required fields marked with *
        name = st.text_input("Your Name *")
        email = st.text_input("Email (serves as ID) *")
        
        st.write("Your Interests:")
        c1, c2, c3 = st.columns(3)
        prefs = []
        
        # Collecting preferences using checkboxes.
        # Note: The values appended (e.g., "Kultur") match the categories in our events database.
        if c1.checkbox("Sport"): prefs.append("Sport")
        if c2.checkbox("Culture"): prefs.append("Cultur")
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Food"): prefs.append("Food")
        if c2.checkbox("Music"): prefs.append("Music")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            # Validation: Ensure required fields are not empty
            if not name.strip():
                st.error("❌ Please enter a name.")
            elif not email.strip():
                st.error("❌ Please enter an email address.")
            else:
                # Save to database
                success, operation = database.add_user(name, email, prefs)
                if success:
                    if operation == "updated":
                        st.success(f"Profile for {name} updated!")
                    else:
                        st.success(f"New profile created for {name}!")
                else: 
                    st.error(f"Error: {operation}")

    st.divider()
    
    # Display existing users so the user knows who is already in the system.
    st.subheader("Current Users in Database")
    users = database.get_all_users()
    if not users:
        st.warning("No users created yet.")
    else:
        for u in users:
            st.text(f"• {u[0]} (Interests: {u[1]})")

def render_card_content(row, time_str, interest_score, avail_score, missing_people, idx, save_callback, color, is_expander=False):
    """
    Helper function to render a single event suggestion card.
    
    Why: We display suggestions in 4 different categories (Gold, Green, Blue, Grey).
    To avoid writing the same UI code 4 times, we put the common layout logic here.
    """
    # Create a 3-column layout for the card content
    c1, c2, c3 = st.columns([1, 2, 1.5])
    
    # Column 1: Time and Category
    c1.write(f"📅 **{time_str}**")
    c1.caption(f"Category: {row['Category']}")
    
    # Column 2: Attendees and matched interests
    c2.write(f"**Interests Matched:** {row['matched_tags']}")
    
    if missing_people:
        c2.caption(f"❌ Missing: {', '.join(missing_people)}")
    
    # Column 3: The Scores (Side-by-Side)
    sc1, sc2 = c3.columns(2)
    with sc1:
        st.write(f"💙 **Interest**")
        st.write(f"**{int(interest_score*100)}%**")
    with sc2:
        st.write(f"🕒 **Availability**")
        st.write(f"**{int(avail_score*100)}%**")
    
    # Additional information (only shown for 'Normal' category expanders)
    if is_expander:
        st.write("**Why this option?**")
        if row['attendee_count'] > 1:
            st.info(f"It works for {row['attendee_count']} people.")
        elif row['matched_tags'] != "General":
            st.info(f"It matches interest: '{row['matched_tags']}'")
        else:
            st.write("It's an available option to consider.")
        
        if row['Description']:
            st.write(f"_{row['Description']}_")

    # The "Add to Calendar" button
    # We use 'key=f"btn_{idx}"' to ensure each button has a unique ID.
    if st.button(f"Add '{row['Title']}' to Calendar", key=f"btn_{idx}"):
        save_callback(row, color, interest_score)

def show_activity_planner():
    """
    Renders the main planning interface.
    Here users connect their calendar, select participants, and run the analysis.
    """
    st.title("📅 Smart Group Planner")
    
    # 1. Authentication
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
        
        # 2. Fetch Calendar Data
        user_busy_map, stats = google_service.fetch_and_map_events(service, all_user_names)
        
        # Diagnostic box to help users debug why events might be missing
        with st.expander("🔍 Diagnostic: Google Calendar Events", expanded=False):
            st.write(f"Google found {stats.get('total_events', 0)} events.")
            if stats.get('unassigned_titles'):
                st.write(f"Ignored: {stats['unassigned_titles']}")

    st.divider()

    # 3. Planning Setup
    all_users_data = database.get_all_users()
    if not all_users_data:
        st.warning("Please create profiles first.")
    else:
        today = datetime.now().date()
        
        # Layout: User selection on left, Week selection on right
        col1, col2 = st.columns(2)
        with col1:
            user_names = [u[0] for u in all_users_data]
            selected = st.multiselect("Who is planning?", user_names, default=user_names)
        
        with col2:
            # Calculate the start (Monday) and end (Sunday) of the selected week
            selected_date = st.date_input("Plan for which week?", value=today)
            start_of_week = selected_date - timedelta(days=selected_date.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            st.caption(f"📅 Showing events for: **{start_of_week.strftime('%d.%m.%Y')} - {end_of_week.strftime('%d.%m.%Y')}**")

        user_prefs_dict = {u[0]: u[1] for u in all_users_data}

        # 4. Run Analysis
        if st.button("🚀 Search Events") and selected:
            # Load local events database
            events_df = recommender.load_local_events("events.csv") 
            if events_df.empty:
                 events_df = recommender.load_local_events("events.xlsx")
            
            # Filter events to only include those in the selected week
            if not events_df.empty:
                events_df['Start'] = pd.to_datetime(events_df['Start'])
                mask = (events_df['Start'].dt.date >= start_of_week) & (events_df['Start'].dt.date <= end_of_week)
                events_df_filtered = events_df.loc[mask].copy()
            else:
                events_df_filtered = events_df

            # Call the Recommender Engine
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
                if st.button("Clear Results"):
                    st.session_state.ranked_results = None
                    st.rerun()
                
                st.markdown("---")
                
                total_group_size = len(selected)

                # Iterate through top 10 results
                for idx, row in ranked_df.head(10).iterrows():
                    # Extract scores safely (using .get to avoid KeyErrors)
                    interest_score = row.get('final_interest_score', 0)
                    avail_score = row.get('availability_score', 0)
                    
                    # Determine categories
                    is_avail_perfect = (avail_score >= 0.99)
                    is_interest_high = (interest_score > 0.6)
                    is_interest_perfect = (interest_score >= 0.99)
                    
                    # Format time nicely (e.g., "Mon 14:00 - 16:00")
                    time_str = f"{row['Start'].strftime('%A, %H:%M')} - {row['End'].strftime('%H:%M')}"

                    # Calculate missing people
                    attending_count = row['attendee_count']
                    missing_people = []
                    if not is_avail_perfect:
                        attending_list = [x.strip() for x in row['attendees'].split(',')]
                        missing_people = [p for p in selected if p not in attending_list]

                    # Define the Callback Function for saving to DB
                    def save_to_db_callback(r, col, score):
                        saved = database.add_saved_event(
                            f"{r['Title']}",
                            r['Start'].strftime("%Y-%m-%dT%H:%M:%S"),
                            r['End'].strftime("%Y-%m-%dT%H:%M:%S"),
                            col,
                            r['Category'],
                            r['attendees'],
                            float(score)
                        )
                        if saved:
                            st.toast(f"Saved '{r['Title']}' permanently to Calendar!")
                        else:
                            st.toast(f"'{r['Title']}' is already saved.")

                    # Render UI based on Category (Gold, Green, Blue, Grey)
                    
                    # 1. THE JACKPOT (Gold)
                    if is_avail_perfect and is_interest_perfect:
                        with st.container(border=True):
                            st.markdown(f"### 🏆 **PERFECT MATCH: {row['Title']}**")
                            st.info("✨ Everyone is free AND it matches everyone's interests perfectly!")
                            render_card_content(row, time_str, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#FFD700")
                    
                    # 2. TIME PERFECT (Green)
                    elif is_avail_perfect:
                        with st.container(border=True):
                            st.markdown(f"### ✅ **GOOD TIMING: {row['Title']}**")
                            st.success("🕒 Everyone is free at this time.")
                            render_card_content(row, time_str, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#28a745")

                    # 3. INTEREST PERFECT (Blue)
                    elif is_interest_high:
                        with st.container(border=True):
                            st.markdown(f"### 💙 **HIGH INTEREST: {row['Title']}**")
                            st.warning(f"⚠️ Only {attending_count}/{total_group_size} people are free, but they will love it!")
                            render_card_content(row, time_str, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#1E90FF")

                    # 4. NORMAL (Grey)
                    else:
                        with st.expander(f"{row['Title']} ({attending_count}/{total_group_size} Ppl)"):
                            render_card_content(row, time_str, interest_score, avail_score, missing_people, idx, save_to_db_callback, "#6c757d", is_expander=True)
            else:
                st.warning("No suitable events found.")

def show_group_calendar():
    """
    Renders the visual calendar combining Google events and saved group activities.
    """
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
        
        # 1. Add Private Google Events
        for i, (user_name, events) in enumerate(user_busy_map.items()):
            color = colors[i % len(colors)]
            for event in events:
                cal_events.append({
                    "title": f"{user_name}: {event.get('summary', 'Termin')}",
                    "start": event['start'].isoformat(),
                    "end": event['end'].isoformat(),
                    "backgroundColor": color,
                    "borderColor": color,
                    "extendedProps": {"category": "Private", "attendees": user_name, "type": "google"}
                })
                
                # Data for charts
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
            
            if st.button("Clear ALL saved activities"):
                database.clear_saved_events()
                st.rerun()

        if cal_events:
            # Render Calendar with Click Callback
            calendar_return = calendar(
                events=cal_events, 
                options={"initialView": "dayGridMonth", "height": 700},
                callbacks=["eventClick"]
            )
            
            # Handle Clicks (Show Popup)
            if calendar_return and "eventClick" in calendar_return:
                clicked_event = calendar_return["eventClick"]["event"]
                props = clicked_event.get("extendedProps", {})
                
                st.markdown("### 📌 Event Details")
                with st.container(border=True):
                    st.markdown(f"## {clicked_event['title']}")
                    
                    c1, c2 = st.columns(2)
                    
                    # Parse ISO time to readable format
                    raw_start = clicked_event.get('start', '')
                    raw_end = clicked_event.get('end', '')
                    try:
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
                        time_display = f"{raw_start} - {raw_end}"
                    
                    c1.write(f"🕒 **Time:** {time_display}")
                    
                    # Display extra info if available (Group Event) vs (Google Event)
                    if "category" in props and props.get("type") != "google":
                        c1.info(f"🏷️ **Category:** {props.get('category', 'General')}")
                        c2.write(f"👥 **Attendees:** {props.get('attendees', 'Unknown')}")
                        score_val = props.get('match_score')
                        if score_val is not None:
                            c2.write(f"💙 **Interest Score:** {int(float(score_val)*100)}%")
                    else:
                        title = clicked_event['title']
                        if ":" in title:
                            person = title.split(":")[0]
                            c2.write(f"👤 **Person:** {person}")
                        else:
                            c2.write("👤 **Type:** Private Calendar Entry")
            
            st.markdown("---")
            # Render Charts
            visualization.show_visualizations(visualization_data)
        else:
            st.info("No events found.")
    else:
        st.warning("Please connect first in the 'Activity Planner'.")
