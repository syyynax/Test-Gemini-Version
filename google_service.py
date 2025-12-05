from datetime import datetime, timedelta

def fetch_and_map_events(service, all_user_names):
    """
    Fetches events from ALL calendars associated with the user's Google account.
    
    Logic:
    1. It retrieves a list of all calendars.
    2. It iterates through each calendar and fetches events (using Pagination to get ALL events).
    3. It attempts to map each event to a specific user.
    
    Returns:
        user_busy_map: A dictionary mapping user names to their list of busy slots.
        stats: A dictionary containing debugging information.
    """
    
    # 1. Define Time Range for API fetch
    # The range is set to look back 30 days (for context/past busy times) and 6 months ahead (for future planning)
    start_dt = datetime.utcnow() - timedelta(days=30)
    end_dt = datetime.utcnow() + timedelta(days=180) # Look 6 months ahead

    # Convert datetimes to the required ISO 8601 format with 'Z' (Zulu/UTC) time zone indicator
    time_min = start_dt.isoformat() + 'Z' 
    time_max = end_dt.isoformat() + 'Z'
    
    # Initialize data structures for results and debugging
    user_busy_map = {name: [] for name in all_user_names} # Final output: busy slots organized by user name 
    debug_unassigned = []  # List of event titles that couldn't be mapped to any user 
    debug_calendars_found = []  # List of all calendar summaries processed
    debug_errors = []           # List of API errors encountered 
    total_events_count = 0
    
    try:
        # API Call: Get a list of all calendars
        calendar_list_result = service.calendarList().list().execute()
        calendars = calendar_list_result.get('items', [])
    except Exception as e:
        # Handle failure to load the initial list of calendars
        return user_busy_map, {"error": f"Could not load calendar list: {e}", "total_events": 0}

    # Iterate through each calendar found
    for cal in calendars:
        cal_id = cal['id']
        cal_summary = cal.get('summary', 'Unknown')
        debug_calendars_found.append(cal_summary)
        
        # --- STEP A: Determine Calendar Ownership ---
        owner_name = None
        cal_summary_clean = cal_summary.lower().strip()
        # Try to match the calendar name/summary against the list of target user names 
        for name in all_user_names:
            user_name_clean = name.lower().strip()
            # Key word matching: Is the user name in the calendar summary, or vice versa?
            if user_name_clean in cal_summary_clean or cal_summary_clean in user_name_clean:
                owner_name = name
                break # Stop checking once an owner is found 
        
        # --- FETCHING EVENTS (With Pagination Loop) ---
        all_raw_events_for_this_cal = []
        page_token = None
        
        try:
            while True:
                # API call: Retrieve events from the current calendar within the time range
                events_result = service.events().list(
                    calendarId=cal_id, 
                    timeMin=time_min, 
                    timeMax=time_max,
                    maxResults=2500,     # Max number of results per page 
                    singleEvents=True,    # Expand recurring events into individual instances 
                    orderBy='startTime',    # Recommended for paginated lists
                    pageToken=page_token     # Token used to fetch the next page of result 
                ).execute()
                
                items = events_result.get('items', [])
                all_raw_events_for_this_cal.extend(items)

                # Check for the next page token to handle caledars with many events 
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break # Stop if no more pages
        except Exception as e:
            debug_errors.append(f"Error reading '{cal_summary}': {str(e)}")
            continue # Skip to the next calendar if this one fails 

        total_events_count += len(all_raw_events_for_this_cal)
        
        # --- PROCESSING  AND ASSIGNING EVENTS ---
        for event in all_raw_events_for_this_cal:
            summary = event.get('summary', f'Event').strip()
            
            # Events can have either 'dateTime' (specifictime) or 'date' (all-day event)
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            end_raw = event['end'].get('dateTime', event['end'].get('date'))
            
            if start_raw and end_raw:
                try:
                    # Date Parsing: Determine if it's a timed event ('T' separator in ISP format) or all-day
                    if "T" in start_raw: 
                        # Timed event (e.g., 2025-12-03T10:00:00+01:00)
                        s_dt = datetime.fromisoformat(start_raw)
                        e_dt = datetime.fromisoformat(end_raw)
                    else: 
                        # All day event (e.g., 2025-12-03)
                        s_dt = datetime.strptime(start_raw, "%Y-%m-%d")
                        e_dt = datetime.strptime(end_raw, "%Y-%m-%d")
                        # All-day events often use the day after the event ends as the 'end' date
                        # For simplicity in availabiltiy checking, we'll keep the full datetime objects. 

                    assigned = False
                    
                    # --- STEP B: Assign Event to User ---
                    
                    # Scenario 1 (High Confidence): Assign to the Calendar Owner 
                    if owner_name:
                        user_busy_map[owner_name].append({
                            'summary': summary, 
                            'start': s_dt, 
                            'end': e_dt
                        })
                        assigned = True
                    
                    # Scenario 2 (Fallback): If no owner was determined, check event title for a *User Keyword Match*
                    else:
                        for name in all_user_names:
                            # If a user's name is found in the event title 
                            if name.strip().lower() in summary.lower():
                                user_busy_map[name].append({
                                    'summary': summary, 
                                    'start': s_dt, 
                                    'end': e_dt
                                })
                                assigned = True
                                # If multiple names are in the title, it will be assigned to all of them 
                   
                    # Log events that could not be assigned to any user 
                    if not assigned:
                        # Limit the size of the debug list to prevent excessive memory usage 
                        if len(debug_unassigned) < 50:
                            debug_unassigned.append(f"Event: '{summary}' | Calendar: '{cal_summary}'")
                
                except ValueError:
                    # Skip events where date/tiem parsing fails 
                    continue 

    # Compile final statistics for debugging and external tracking 
    stats = {
        "total_events": total_events_count,
        "assigned": total_events_count - len(debug_unassigned),
        "unassigned_titles": debug_unassigned,
        "calendars_found": debug_calendars_found,
        "errors": debug_errors
    }
    
    return user_busy_map, stats
