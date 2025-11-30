def show_visualizations(events_list):
    """
    Main function to render the visualization section.
    """
    st.markdown("### 📊 Data Visualization")
    st.caption("See how busy you are this week and who among you is the busiest.")
    
    df = events_to_df(events_list)

    if df.empty:
        st.info("No data available to visualize.")
        return

    # Date Filter
    min_date = df["start"].min().date()
    max_date = df["start"].max().date()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Standard: Nur die nächste Woche (7 Tage) vorauswählen, nicht den ganzen Monat
        default_end = min_date + pd.Timedelta(days=7)
        if default_end > max_date: default_end = max_date
        
        dates = st.date_input(
            "Filter Time Range",
            value=(min_date, default_end),
            min_value=min_date,
            max_value=max_date
        )

    # Validate Date Input
    if isinstance(dates, tuple) and len(dates) == 2:
        start_date, end_date = dates
    else:
        st.info("Please select a start and end date.")
        return # Waiting for second date

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Initialize Session State for chart visibility
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
            st.warning(f"No events found between {start_date} and {end_date}.")
        else:
            # Info Text: Zeige an, wie viele Events gefiltert wurden
            st.caption(f"Showing {len(df_filtered)} events in selected timeframe.")
            
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
