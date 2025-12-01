from datetime import datetime, timedelta

def fetch_and_map_events(service, all_user_names):
    """
    Fetches events from ALL calendars associated with the user's Google account.
    
    Logic:
    1. It retrieves a list of all calendars (primary, shared, subscribed).
    2. It iterates through each calendar and fetches events starting from 30 days ago.
    3. It attempts to map each event to a specific user in our app ('all_user_names').
       - Ideally, we check if the calendar itself belongs to a user (e.g., "Mia's Calendar").
       - If not, we check if the user's name appears in the event title (e.g., "Dentist Mia").
    
    Returns:
        user_busy_map: A dictionary mapping user names to their list of busy slots.
        stats: A dictionary containing debugging information (total events found, errors, etc.).
    """
    
    # 1. Define Time Range: Look back 30 days to include recent history and future events.
    # We use UTC to ensure consistency across timezones.
    start_dt = datetime.utcnow() - timedelta(days=30)
    end_dt = datetime.utcnow() + timedelta(days=180)

    time_min = start_dt.isoformat() + 'Z' 
    time_max = end_dt.isoformat() + 'Z'
    
    # Initialize data structures to store results and debug info
    user_busy_map = {name: [] for name in all_user_names}
    debug_unassigned = []       # List of events that couldn't be assigned to any user
    debug_calendars_found = []  # List of calendar names we successfully found
    debug_errors = []           # List of errors encountered (e.g., permission issues)
    total_events_count = 0
    
    try:
        # API Call: Get a list of all calendars the user has access to.
        calendar_list_result = service.calendarList().list().execute()
        calendars = calendar_list_result.get('items', [])
    except Exception as e:
        # If we can't even get the list of calendars, return an error immediately.
        return user_busy_map, {"error": f"Could not load calendar list: {e}", "total_events": 0}

    # Iterate through each calendar found
    for cal in calendars:
        cal_id = cal['id']
        cal_summary = cal.get('summary', 'Unknown') # The display name of the calendar
        debug_calendars_found.append(cal_summary)
        
        # --- STEP A: Determine Calendar Ownership ---
        # We try to guess if this entire calendar belongs to one of our app users.
        # This is a "Smart Match": If the calendar is named "Mia's Schedule", 
        # we assume all events in it belong to the user "Mia".
        owner_name = None
        
        # Clean up the calendar name for easier comparison (lowercase, remove spaces)
        cal_summary_clean = cal_summary.lower().strip()
        
        for name in all_user_names:
            # Clean up the user name from our database
            user_name_clean = name.lower().strip()
            
            # Check if the user name is part of the calendar name, or vice versa.
            # Example: "Mia" in "Mia's Calendar" -> Match!
            if user_name_clean in cal_summary_clean or cal_summary_clean in user_name_clean:
                owner_name = name
                break # We found the owner, stop searching
        
        try:
            # API Call: Fetch events for THIS specific calendar
            events_result = service.events().list(
                calendarId=cal_id, 
                timeMin=time_min, 
                maxResults=50,      # Limit to 50 events per calendar to avoid hitting API limits
                singleEvents=True,  # Expand recurring events into individual instances
                orderBy='startTime',
                pageToken=page_token
            ).execute()
            
            items = events_result.get('items', [])
                all_raw_events_for_this_cal.extend(items)
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break

            total_events_count += len(all_raw_events_for_this_cal)
            
            for event in raw_events:
                summary = event.get('summary', f'Event').strip()
                
                # Get start and end times.
                # Google uses 'dateTime' for timed events and 'date' for all-day events.
                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                end_raw = event['end'].get('dateTime', event['end'].get('date'))
                
                # Only process events that have valid start/end times
                if start_raw and end_raw:
                    try:
                        # Date Parsing Logic
                        # We need to convert Google's string format into Python datetime objects
                        if "T" in start_raw: 
                            # Format: "YYYY-MM-DDTHH:MM:SS" (Timed event)
                            s_dt = datetime.fromisoformat(start_raw)
                            e_dt = datetime.fromisoformat(end_raw)
                        else: 
                            # Format: "YYYY-MM-DD" (All-day event)
                            # We default to midnight for calculation purposes
                            s_dt = datetime.strptime(start_raw, "%Y-%m-%d")
                            e_dt = datetime.strptime(end_raw, "%Y-%m-%d")

                        assigned = False
                        
                        # --- STEP B: Assign Event to User ---
                        
                        # Scenario 1: We already know the calendar owner (from Step A).
                        # If the calendar belongs to "Mia", this event automatically belongs to "Mia".
                        if owner_name:
                            user_busy_map[owner_name].append({
                                'summary': summary, 
                                'start': s_dt, 
                                'end': e_dt
                            })
                            assigned = True
                        
                        # Scenario 2: It's a shared/general calendar (e.g. "Family").
                        # We look for the user's name inside the event title (e.g., "Dentist Mia").
                        else:
                            for name in all_user_names:
                                if name.strip().lower() in summary.lower():
                                    user_busy_map[name].append({
                                        'summary': summary, 
                                        'start': s_dt, 
                                        'end': e_dt
                                    })
                                    assigned = True
                        
                        # If we couldn't assign the event to anyone, we log it for debugging.
                        if not assigned:
                            debug_unassigned.append(f"Event: '{summary}' | Calendar: '{cal_summary}' (No match with users: {all_user_names})")
                    
                    except ValueError:
                        # Skip events with weird date formats we can't parse
                        continue 

        except Exception as e:
            # If we can't read a specific calendar (e.g. permission denied), log error and continue to next.
            debug_errors.append(f"Error reading '{cal_summary}': {str(e)}")
            continue
                
    # Compile statistics for the frontend diagnostic box
    stats = {
        "total_events": total_events_count,
        "assigned": total_events_count - len(debug_unassigned),
        "unassigned_titles": debug_unassigned,
        "calendars_found": debug_calendars_found,
        "errors": debug_errors
    }
    
    return user_busy_map, stats
