import streamlit as st
import database
import auth
import google_service
import recommender
from streamlit_calendar import calendar
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="Meetly", page_icon="👋", layout="wide")
database.init_db()
# --- SIDEBAR ---
st.sidebar.title("Navigation")
# "Start" is now the first option (Default)
# Translating UI to English as requested
page = st.sidebar.radio("Go to", ["Start", "Profiles", "Activity Planner", "Group Calendar"])

# --- PAGE 0: START PAGE (NEW) ---
if page == "Start":
    # Centered Title and Header for better aesthetics
    st.markdown("<h1 style='text-align: center;'>✨ Welcome to Meetly! ✨</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>The App to finally bring your friends together.</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # A short guide to make the app feel "complete"
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

# --- PAGE 1: PROFILE ---
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
        if c2.checkbox("Culture"): prefs.append("Kultur") # Keeping DB value keys stable
        if c3.checkbox("Party"): prefs.append("Party")
        if c1.checkbox("Food"): prefs.append("Essen")
        if c2.checkbox("Education"): prefs.append("Education")
        if c3.checkbox("Outdoor"): prefs.append("Outdoor")
        
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            # --- VALIDATION ---
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
