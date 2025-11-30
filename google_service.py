from datetime import datetime, timedelta

def fetch_and_map_events(service, all_user_names):
    """
    Holt Events aus ALLEN Kalendern.
    Logik: Wenn ein Kalender einem User gehört (Name im Kalender-Titel),
    dann werden ALLE Termine daraus diesem User zugeordnet.
    """
    # 1. Zeitraum: 30 Tage zurück bis Zukunft
    start_dt = datetime.utcnow() - timedelta(days=30)
    time_min = start_dt.isoformat() + 'Z'
    
    user_busy_map = {name: [] for name in all_user_names}
    debug_unassigned = [] 
    debug_calendars_found = [] 
    debug_errors = [] 
    total_events_count = 0
    
    try:
        # Liste aller Kalender holen
        calendar_list_result = service.calendarList().list().execute()
        calendars = calendar_list_result.get('items', [])
    except Exception as e:
        return user_busy_map, {"error": f"Konnte Kalender-Liste nicht laden: {e}", "total_events": 0}

    # Durch jeden Kalender gehen
    for cal in calendars:
        cal_id = cal['id']
        cal_summary = cal.get('summary', 'Unbekannt') # Name des Kalenders (z.B. "Mia's Kalender")
        debug_calendars_found.append(cal_summary)
        
        # --- SCHRITT A: Wem gehört dieser Kalender? ---
        # Wir prüfen, ob einer unserer App-User im Kalender-Namen vorkommt.
        owner_name = None
        
        # Bereinigen des Kalender-Namens für den Vergleich
        cal_summary_clean = cal_summary.lower().strip()
        
        for name in all_user_names:
            # Bereinigen des User-Namens
            user_name_clean = name.lower().strip()
            
            # Prüfen: Ist 'mia' in 'mia's kalender'? ODER ist 'mia muster' in 'mia'?
            # Wir prüfen in beide Richtungen für maximale Trefferquote
            if user_name_clean in cal_summary_clean or cal_summary_clean in user_name_clean:
                owner_name = name
                break # Gefunden!
        
        try:
            events_result = service.events().list(
                calendarId=cal_id, 
                timeMin=time_min, 
                maxResults=50, 
                singleEvents=True, 
                orderBy='startTime'
            ).execute()
            
            raw_events = events_result.get('items', [])
            total_events_count += len(raw_events)
            
            for event in raw_events:
                summary = event.get('summary', f'Termin').strip()
                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                end_raw = event['end'].get('dateTime', event['end'].get('date'))
                
                if start_raw and end_raw:
                    try:
                        # Datum parsing
                        if "T" in start_raw: 
                            s_dt = datetime.fromisoformat(start_raw)
                            e_dt = datetime.fromisoformat(end_raw)
                        else: 
                            s_dt = datetime.strptime(start_raw, "%Y-%m-%d")
                            e_dt = datetime.strptime(end_raw, "%Y-%m-%d")

                        assigned = False
                        
                        # --- SCHRITT B: Zuordnung ---
                        # 1. Wenn wir den Kalender-Besitzer kennen (aus Schritt A),
                        #    gehört der Termin automatisch ihm.
                        if owner_name:
                            user_busy_map[owner_name].append({
                                'summary': summary, 
                                'start': s_dt, 
                                'end': e_dt
                            })
                            assigned = True
                        
                        # 2. Fallback: Wir suchen Namen im Termin-Titel
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
                            # Debug-Info erweitert, damit wir sehen WARUM es ignoriert wurde
                            debug_unassigned.append(f"Event: '{summary}' | Kalender: '{cal_summary}' (Kein Match mit Usern: {all_user_names})")
                    
                    except ValueError:
                        continue 

        except Exception as e:
            debug_errors.append(f"Fehler bei '{cal_summary}': {str(e)}")
            continue
                
    stats = {
        "total_events": total_events_count,
        "assigned": total_events_count - len(debug_unassigned),
        "unassigned_titles": debug_unassigned,
        "calendars_found": debug_calendars_found,
        "errors": debug_errors
    }
    
    return user_busy_map, stats
