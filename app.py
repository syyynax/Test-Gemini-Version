# This is our main entry point for the Streamlit application. 
# Key concepts:
# - Core application setup
# - Database initialization
# - Management of the session state 
# - Page navigation controlling based on user selections 


import streamlit as st
import database
import views

# --- SETUP ---
# Configure the Streamlit page with a title, icon, and layout.
st.set_page_config(page_title="Meetly", page_icon="👋", layout="wide")

# Initialize the database (create tables if they don't exist).
# This ensures that 'users' and 'saved_events' tables exist before the app tries to access them. 
database.init_db()

# --- SESSION STATE INITIALIZATION ---
# Session state is crucial in Streamlit persisting data across user interactions
# (e.g., button clicks, widget changes) that trigger application reruns. 

# 'ranked_results' stores the final, scored list of recommended events from the engine.
if 'ranked_results' not in st.session_state:
    st.session_state.ranked_results = None # Initially none, unitl the recommendation process runs 

# 'selected_events' stores events the user has chosen to add to the group calendar.
if 'selected_events' not in st.session_state:
    st.session_state.selected_events = []

# --- NAVIGATION LOGIC ---
# 'nav_page' keeps track of the current page in the sidebar.
# Default is 'Start' for initial landing
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Start"

# If the URL contains an authorization 'code' (from Google Login),
# automatically redirect the user to the 'Activity Planner' page to continue the flow.
if st.query_params.get("code"):
    st.session_state.nav_page = "Activity Planner"

# --- SIDEBAR UI AND NAVIGATION ---
st.sidebar.title("Navigation")

# Create a radio button menu for navigation, placed in the sidebar.
# The 'key = "nav_page"' links the user's selection directly to the st.session state.
page = st.sidebar.radio(
    "Go to", 
    ["Start", "Profiles", "Activity Planner", "Group Calendar"],
    key="nav_page" # The radio selection updates st.session_state.nav_page
)

# --- ROUTING ---
# The main content area renders different views based on the value of st.session_state.nav_page.
# This structure delegates the rendering logic to the corresponding functions in the 'views.py' module.

if page == "Start":
    # The application landing page.
    views.show_start_page()

elif page == "Profiles":
    # Page for managing user preferences and viewing current users.
    views.show_profiles_page()

elif page == "Activity Planner":
    # The core recommendation and scheduling page where availability is checked.
    views.show_activity_planner()

elif page == "Group Calendar":
    # Displays the finalized (saved) events in a calendar. 
    views.show_group_calendar()
