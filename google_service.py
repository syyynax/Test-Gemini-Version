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
    
    # 1. Define Time Range
    start_dt = datetime.utcnow() - timedelta(days=30)
    end_dt = datetime.utcnow() + timedelta(days=180) # Look 6 months ahead

    time_min = start_dt.isoformat() + 'Z' 
    time_max = end_dt.isoformat() + 'Z'
    
    # Initialize data structures
    user_busy_map = {name: [] for name in all_user_names}
    debug_unassigned = []       
    debug_calendars_found = []  
    debug_errors = []           
    total_events_count = 0
    
    try:
        # API Call: Get a list of all calendars
        calendar_list_result = service.calendarList().list().execute()
        calendars = calendar_list_result.get('items', [])
    except Exception as e:
        return user_busy_map, {"error": f"Could not load calendar list: {e}", "total_events": 0}

    # Iterate through each calendar found
    for cal in calendars:
        cal_id = cal['id']
        cal_summary = cal.get('summary', 'Unknown')
        debug_calendars_found.append(cal_summary)
        
        # --- STEP A: Determine Calendar Ownership ---
        owner_name = None
        cal_summary_clean = cal_summary.lower().strip()
        
        for name in all_user_names:
            user_name_clean = name.lower().strip()
            if user_name_clean in cal_summary_clean or cal_summary_clean in user_name_clean:
                owner_name = name
                break 
        
        # --- FETCHING EVENTS (With Pagination Loop) ---
        all_raw_events_for_this_cal = []
        page_token = None
        
        try:
            while True:
                events_result = service.events().list(
                    calendarId=cal_id, 
                    timeMin=time_min, 
                    timeMax=time_max,
                    maxResults=2500,     
                    singleEvents=True, 
                    orderBy='startTime',
                    pageToken=page_token 
                ).execute()
                
                items = events_result.get('items', [])
                all_raw_events_for_this_cal.extend(items)
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break # Stop if no more pages
        except Exception as e:
            debug_errors.append(f"Error reading '{cal_summary}': {str(e)}")
            continue

        total_events_count += len(all_raw_events_for_this_cal)
        
        # --- PROCESSING EVENTS ---
        for event in all_raw_events_for_this_cal:
            summary = event.get('summary', f'Event').strip()
            
            # Get start and end times
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            end_raw = event['end'].get('dateTime', event['end'].get('date'))
            
            if start_raw and end_raw:
                try:
                    # Date Parsing
                    if "T" in start_raw: 
                        s_dt = datetime.fromisoformat(start_raw)
                        e_dt = datetime.fromisoformat(end_raw)
                    else: 
                        s_dt = datetime.strptime(start_raw, "%Y-%m-%d")
                        e_dt = datetime.strptime(end_raw, "%Y-%m-%d")

                    assigned = False
                    
                    # --- STEP B: Assign Event to User ---
                    
                    # Scenario 1: Calendar Owner match
                    if owner_name:
                        user_busy_map[owner_name].append({
                            'summary': summary, 
                            'start': s_dt, 
                            'end': e_dt
                        })
                        assigned = True
                    
                    # Scenario 2: Keyword match in title
                    else:
                        for name in all_user_names:
                            if name.strip().lower() in summary.lower():
                                user_busy_map[name].append({
                                    'summary': summary, 
                                    'start': s_dt, 
                                    'end': e_dt
                                })
                                assigned = True
                    
                    if not assigned:
                        # Limit debug output to avoid massive logs
                        if len(debug_unassigned) < 50:
                            debug_unassigned.append(f"Event: '{summary}' | Calendar: '{cal_summary}'")
                
                except ValueError:
                    continue 

    # Compile statistics
    stats = {
        "total_events": total_events_count,
        "assigned": total_events_count - len(debug_unassigned),
        "unassigned_titles": debug_unassigned,
        "calendars_found": debug_calendars_found,
        "errors": debug_errors
    }
    
    return user_busy_map, stats
