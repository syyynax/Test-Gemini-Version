import streamlit as st
import database
import views

# --- SETUP ---
# Configure the Streamlit page with a title, icon, and layout.
st.set_page_config(page_title="Meetly", page_icon="👋", layout="wide")

# Initialize the database (create tables if they don't exist).
database.init_db()

# --- SESSION STATE INITIALIZATION ---
# Initialize session state variables to persist data across reruns.

# 'ranked_results' stores the output of the recommendation engine.
if 'ranked_results' not in st.session_state:
    st.session_state.ranked_results = None

# 'selected_events' stores events the user has chosen to add to the group calendar.
if 'selected_events' not in st.session_state:
    st.session_state.selected_events = []

# --- NAVIGATION LOGIC ---
# 'nav_page' keeps track of the current page in the sidebar.
# Default is 'Start'.
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Start"

# If the URL contains an authorization 'code' (from Google Login),
# automatically redirect the user to the 'Activity Planner' page.
if st.query_params.get("code"):
    st.session_state.nav_page = "Activity Planner"

# --- SIDEBAR ---
st.sidebar.title("Navigation")

# Create a radio button menu for navigation.
# The 'key' argument binds this widget to 'st.session_state.nav_page'.
page = st.sidebar.radio(
    "Go to", 
    ["Start", "Profiles", "Activity Planner", "Group Calendar"],
    key="nav_page"
)

# --- ROUTING ---
# Call the appropriate view function based on the selected page.

if page == "Start":
    views.show_start_page()

elif page == "Profiles":
    views.show_profiles_page()

elif page == "Activity Planner":
    views.show_activity_planner()

elif page == "Group Calendar":
    views.show_group_calendar()
