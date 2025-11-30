import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns

# Set style for charts (gives a nice dark grid background)
sns.set_theme(style="darkgrid")

def events_to_df(events_list):
    """
    Converts a list of event dictionaries (from Google Calendar or Database) into a pandas DataFrame.
    This is necessary because plotting libraries work best with DataFrames.
    
    Expects dictionary keys: 'start', 'end', 'summary' (or 'title'), and optionally 'person'.
    """
    df = pd.DataFrame(events_list)

    if df.empty:
        return pd.DataFrame()

    # Ensure datetime format for start and end columns so we can do date math
    if "start" in df.columns:
        df["start"] = pd.to_datetime(df["start"])
    if "end" in df.columns:
        df["end"] = pd.to_datetime(df["end"])
    
    # Fallback: Use 'summary' as 'title' if 'title' is missing (Google API uses 'summary')
    if "title" not in df.columns and "summary" in df.columns:
        df["title"] = df["summary"]
    
    # If 'person' is not explicitly provided, try to extract it from the title.
    # Example: "Mia: Dentist" -> Person is "Mia"
    if "person" not in df.columns:
        df["person"] = df["title"].apply(lambda x: x.split(":")[0] if isinstance(x, str) else "Unknown")
        
    # Calculate the Weekday name (e.g., "Monday") for analysis
    if "start" in df.columns:
        df["weekday"] = df["start"].dt.day_name()

    return df

def plot_events_per_person(df):
    """
    Generates a bar chart showing how many events each person has.
    """
    if df.empty or "person" not in df.columns:
        st.warning("Not enough data to plot events per person.")
        return

    # Count occurrences of each person
    counts = df["person"].value_counts()

    fig, ax = plt.subplots(figsize=(8, 4))
    # Use seaborn barplot for better aesthetics and colors (viridis palette)
    sns.barplot(x=counts.index, y=counts.values, ax=ax, palette="viridis")

    ax.set_title("Number of Events by Person (Selected Timeframe)")
    ax.set_ylabel("Events")
    ax.set_xlabel("Person")
    plt.xticks(rotation=45) # Rotate names to prevent overlapping

    st.pyplot(fig) # Render the plot in Streamlit

def plot_events_per_weekday(df):
    """
    Generates a line chart showing the distribution of events across the week.
    Useful to see which days are busiest.
    """
    if df.empty or "weekday" not in df.columns:
        st.warning("Not enough data to plot events by weekday.")
        return

    # Define the correct order of days (otherwise they might be sorted alphabetically)
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    df["weekday"] = pd.Categorical(df["weekday"], categories=order, ordered=True)
    
    # Count events per weekday and sort by the day order defined above
    weekday_counts = df["weekday"].value_counts().sort_index()

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.lineplot(x=weekday_counts.index, y=weekday_counts.values, marker="o", ax=ax, sort=False)

    ax.set_title("Events by Weekday (Selected Timeframe)")
    ax.set_ylabel("Events")
    ax.set_xlabel("Weekday")
    
    # Force integer ticks on y-axis (you can't have 1.5 events)
    from matplotlib.ticker import MaxNLocator
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    
    st.pyplot(fig)

def show_visualizations(events_list):
    """
    Main function to render the visualization section in the Streamlit app.
    """
    st.markdown("### 📊 Data Visualization")
    st.caption("See how busy you are this week and who among you is the busiest.")
    
    df = events_to_df(events_list)

    if df.empty:
        st.info("No data available to visualize.")
        return

    # Determine the full range of dates available in the data
    min_date = df["start"].min().date()
    max_date = df["start"].max().date()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Set default view to the next 7 days to avoid cluttering the chart with duplicates
        default_end = min_date + pd.Timedelta(days=7)
        if default_end > max_date: default_end = max_date
        
        # Date Range Picker
        dates = st.date_input(
            "Filter Time Range",
            value=(min_date, default_end),
            min_value=min_date,
            max_value=max_date
        )

    # Validate Date Input (User must pick both start and end)
    if isinstance(dates, tuple) and len(dates) == 2:
        start_date, end_date = dates
    else:
        st.info("Please select a start and end date.")
        return 

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Initialize Session State for chart visibility (toggle button)
    if "show_plot" not in st.session_state:
        st.session_state.show_plot = False

    # Button to show/refresh charts
    if st.button("Generate / Refresh Charts"):
        st.session_state.show_plot = True

    if st.session_state.show_plot:
        st.divider()
        
        # Filter DataFrame based on user selection
        mask = (df["start"].dt.date >= start_date) & (df["start"].dt.date <= end_date)
        df_filtered = df[mask]

        if df_filtered.empty:
            st.warning(f"No events found between {start_date} and {end_date}.")
        else:
            # Show user how many events are included in the analysis
            st.caption(f"Showing {len(df_filtered)} events in selected timeframe.")
            
            # Radio button to switch between chart types
            chart_type = st.radio(
                "Select Visualization:",
                ["Events by Person", "Events by Weekday"],
                horizontal=True
            )

            # Render the selected chart
            if chart_type == "Events by Person":
                plot_events_per_person(df_filtered)
            elif chart_type == "Events by Weekday":
                plot_events_per_weekday(df_filtered)
