from datetime import datetime

def fetch_and_map_events(service, all_user_names):
    """
    Holt Events aus dem Google Kalender und ordnet sie Usern zu.
    
    Args:
        service: Das Google API Service Objekt
        all_user_names: Liste aller bekannten Usernamen aus der DB
        
    Returns:
        user_busy_map: Dictionary {'Max': [{'start':..., 'end':...}], ...}
        stats: Dictionary mit Statistiken (Anzahl Events etc.)
    """
    # 1. Zeitraum definieren (Heute bis in 30 Tagen)
    now = datetime.utcnow().isoformat() + 'Z'
    
    # 2. API Aufruf
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now, 
        maxResults=100, 
        singleEvents=True, 
        orderBy='startTime'
    ).execute()
    
    raw_events = events_result.get('items', [])
    
    # 3. Mapping Logik: Welches Event gehört wem?
    user_busy_map = {name: [] for name in all_user_names}
    unassigned_count = 0
    
    for event in raw_events:
        summary = event.get('summary', '').lower()
        start = event['start'].get('dateTime')
        end = event['end'].get('dateTime')
        
        # Ignoriere Ganztagesevents (haben kein dateTime)
        if start and end: 
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            
            assigned = False
            for name in all_user_names:
                # Check: Ist der Name im Titel enthalten? (Case insensitive)
                if name.lower() in summary:
                    user_busy_map[name].append({
                        'start': start_dt, 
                        'end': end_dt
                    })
                    assigned = True
            
            if not assigned:
                unassigned_count += 1
                
    stats = {
        "total_events": len(raw_events),
        "unassigned": unassigned_count
    }
    
    return user_busy_map, stats
