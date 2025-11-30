import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

# Set style for charts
sns.set_theme(style="darkgrid")

def events_to_df(google_events):
    """
    Converts a list of event dictionaries into a pandas DataFrame.
    """
    df = pd.DataFrame(google_events)

    if df.empty:
        return pd.DataFrame()

    # Ensure datetime format
    if "start" in df.columns:
        df["start"] = pd.to_datetime(df["start"])
    if "end" in df.columns:
        df["end"] = pd.to_datetime(df["end"])
    
    # Fallback for Title
    if "title" not in df.columns and "summary" in df.columns:
        df["title"] = df["summary"]
    
    # IMPROVEMENT: Only try to extract person from title if it's not already provided
    if "person" not in df.columns:
        df["person"] = df["title"].apply(lambda x: x.split(":")[0] if isinstance(x, str) else "Unknown")
        
    # Calculate Weekday
    if "start" in df.columns:
        df["weekday"] = df["start"].dt.day_name()

    return df

def plot_events_per_person(df):
    if df.empty or "person" not in df.columns:
        st.warning("Not enough data to plot events per person.")
        return

    counts = df["person"].value_counts()

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(x=counts.index, y=counts.values, ax=ax, palette="viridis")

    ax.set_title("Number of Events by Person")
    ax.set_ylabel("Count")
    ax.set_xlabel("Person")
    plt.xticks(rotation=45) # Rotate names if they are long

    st.pyplot(fig)

def plot_events_per_weekday(df):
    if df.empty or "weekday" not in df.columns:
        st.warning("Not enough data to plot events by weekday.")
        return

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    # Ensure correct order
    df["weekday"] = pd.Categorical(df["weekday"], categories=order, ordered=True)
    weekday_counts = df["weekday"].value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.lineplot(x=weekday_counts.index, y=weekday_counts.values, marker="o", ax=ax, sort=False)

    ax.set_title("Busy Times: Events by Weekday")
    ax.set_ylabel("Total Events")
    ax.set_xlabel("Day of Week")
    
    st.pyplot(fig)

def show_visualizations(google_events):
    """
    Main function to render the visualization section.
    """
    st.markdown("### 📊 Data Visualization")
    st.caption("See how busy you are this week and who among you is the busiest.") # DEIN NEUER UNTERTITEL
    
    df = events_to_df(google_events)

    if df.empty:
        st.info("No data available to visualize.")
        return

    # Date Filter
    min_date = df["start"].min().date()
    max_date = df["start"].max().date()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        dates = st.date_input(
            "Filter Time Range",
            value=(min_date, max_date)
        )

    # Validate Date Input
    if isinstance(dates, tuple) and len(dates) == 2:
        start_date, end_date = dates
    else:
        # If user is still selecting
        return

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Initialize Session State for the chart visibility
    if "show_plot" not in st.session_state:
        st.session_state.show_plot = False

    # Chart Generation Button
    if st.button("Generate / Refresh Charts"):
        st.session_state.show_plot = True

    if st.session_state.show_plot:
        st.divider()
        
        # Filter Data
        mask = (df["start"].dt.date >= start_date) & (df["start"].dt.date <= end_date)
        df_filtered = df[mask]

        if df_filtered.empty:
            st.warning("No events found in this date range.")
        else:
            # Dropdown for Chart Type
            chart_type = st.radio(
                "Select Visualization:",
                ["Events by Person", "Events by Weekday"],
                horizontal=True
            )

            if chart_type == "Events by Person":
                plot_events_per_person(df_filtered)
            elif chart_type == "Events by Weekday":
                plot_events_per_weekday(df_filtered)
