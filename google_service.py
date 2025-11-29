from datetime import datetime, timedelta

def fetch_and_map_events(service, all_user_names):
    """
    Holt Events aus ALLEN Kalendern des Users (nicht nur 'primary').
    Sucht ab heute Mitternacht (UTC).
    """
    # 1. Zeitraum: Ab heute Mitternacht
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    time_min = today_start.isoformat() + 'Z'
    
    user_busy_map = {name: [] for name in all_user_names}
    debug_unassigned = [] 
    total_events_count = 0
    
    # 2. SCHRITT A: Liste aller Kalender holen
    # Wir fragen: "Welche Kalender hat dieser User?"
    calendar_list_result = service.calendarList().list().execute()
    calendars = calendar_list_result.get('items', [])

    # 3. SCHRITT B: Durch jeden Kalender iterieren
    for cal in calendars:
        cal_id = cal['id']
        cal_summary = cal.get('summary', 'Unbekannt')
        
        # Optional: Nur ausgewählte Kalender? Hier nehmen wir einfach ALLE.
        # Man könnte z.B. Kalender ignorieren, die "Feiertage" heißen.
        
        try:
            # Events für DIESEN spezifischen Kalender holen
            events_result = service.events().list(
                calendarId=cal_id, 
                timeMin=time_min, 
                maxResults=50, # Limit pro Kalender, um API-Limits zu schonen
                singleEvents=True, 
                orderBy='startTime'
            ).execute()
            
            raw_events = events_result.get('items', [])
            total_events_count += len(raw_events)
            
            for event in raw_events:
                # Titel holen (Fallback: Kalender-Name nutzen, falls Event keinen Titel hat)
                summary = event.get('summary', f'Termin ({cal_summary})').strip()
                
                # Start/Ende holen
                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                end_raw = event['end'].get('dateTime', event['end'].get('date'))
                
                if start_raw and end_raw:
                    try:
                        # Datum parsing Logik
                        if "T" in start_raw: 
                            s_dt = datetime.fromisoformat(start_raw)
                            e_dt = datetime.fromisoformat(end_raw)
                        else: # Ganztägig
                            s_dt = datetime.strptime(start_raw, "%Y-%m-%d")
                            e_dt = datetime.strptime(end_raw, "%Y-%m-%d")

                        assigned = False
                        
                        # Prüfen ob ein User-Name im Titel steckt
                        for name in all_user_names:
                            if name.strip().lower() in summary.lower():
                                user_busy_map[name].append({
                                    'summary': summary, 
                                    'start': s_dt, 
                                    'end': e_dt
                                })
                                assigned = True
                        
                        if not assigned:
                            debug_unassigned.append(f"{summary} (aus Kalender: {cal_summary})")
                    
                    except ValueError:
                        continue 

        except Exception as e:
            # Manchmal fehlen Rechte für bestimmte abonnierten Kalender, einfach weitermachen
            print(f"Konnte Kalender {cal_summary} nicht lesen: {e}")
            continue
                
    stats = {
        "total_events": total_events_count,
        "assigned": total_events_count - len(debug_unassigned),
        "unassigned_titles": debug_unassigned 
    }
    
    return user_busy_map, stats
