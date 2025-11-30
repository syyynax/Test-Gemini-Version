import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta, time
import os

# --- MACHINE LEARNING & LOGIK ---

def load_local_events(file_path="events.xlsx"):
    """
    Lädt Events aus einer Datei (Excel oder CSV).
    """
    generated_events = []
    
    try:
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        if 'weekday' in df.columns and 'event_name' in df.columns:
            today = datetime.now().date()
            for i in range(30):
                current_date = today + timedelta(days=i)
                current_weekday = current_date.weekday()
                
                days_events = df[df['weekday'] == current_weekday]
                
                for _, row in days_events.iterrows():
                    try:
                        s_val = row['start_time']
                        e_val = row['end_time']

                        if isinstance(s_val, time): s_time = s_val
                        else: s_time = pd.to_datetime(str(s_val)).time()

                        if isinstance(e_val, time): e_time = e_val
                        else: 
                            try: e_time = pd.to_datetime(str(e_val)).time()
                            except: e_time = time(0, 0)
                        
                        start_dt = datetime.combine(current_date, s_time)
                        
                        if e_time <= s_time and e_time != time(0,0):
                             end_dt = datetime.combine(current_date + timedelta(days=1), e_time)
                        elif e_time == time(0,0):
                             end_dt = datetime.combine(current_date + timedelta(days=1), e_time)
                        else:
                            end_dt = datetime.combine(current_date, e_time)

                        cat = "Allgemein"
                        if 'category' in row: cat = row['category']
                        elif 'kategorie' in row: cat = row['kategorie']

                        generated_events.append({
                            'Title': row['event_name'],
                            'Start': start_dt,
                            'End': end_dt,
                            'Category': cat, 
                            'Description': f"Ort: {row.get('location', 'Unbekannt')}"
                        })
                    except Exception as e:
                        continue
                        
            return pd.DataFrame(generated_events)
        else:
            if 'Start' in df.columns:
                df['Start'] = pd.to_datetime(df['Start']).dt.tz_localize(None)
            if 'End' in df.columns:
                df['End'] = pd.to_datetime(df['End']).dt.tz_localize(None)
            return df

    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return pd.DataFrame()

def check_user_availability(event_start, event_end, user_busy_slots):
    for busy in user_busy_slots:
        b_start = busy['start'].replace(tzinfo=None)
        b_end = busy['end'].replace(tzinfo=None)
        if (event_start < b_end) and (event_end > b_start):
            return False 
    return True

def find_best_slots_for_group(events_df, user_busy_map, selected_users, all_user_prefs, min_attendees=1):
    """
    Findet Events und berechnet Details zu Übereinstimmungen.
    """
    if events_df.empty:
        return pd.DataFrame()

    results = []

    for _, event in events_df.iterrows():
        attendees = []
        
        # 1. Wer hat Zeit?
        for user in selected_users:
            busy_slots = user_busy_map.get(user, [])
            if check_user_availability(event['Start'], event['End'], busy_slots):
                attendees.append(user)
        
        if len(attendees) >= min_attendees:
            
            # 2. Welche Interessen passen? (Detail-Analyse PRO PERSON)
            attendee_prefs_list = []
            matched_tags = set()
            event_text = (str(event.get('Category', '')) + " " + str(event.get('Description', '')) + " " + str(event['Title'])).lower()
            
            # Zähler für glückliche User
            happy_user_count = 0
            
            for attendee in attendees:
                u_prefs = all_user_prefs.get(attendee, "")
                attendee_prefs_list.append(u_prefs)
                
                # Checke ob DIESER User das Event mag
                user_likes_event = False
                for pref in u_prefs.split(','):
                    clean_pref = pref.strip()
                    if clean_pref and clean_pref.lower() in event_text:
                        matched_tags.add(clean_pref)
                        user_likes_event = True
                
                if user_likes_event:
                    happy_user_count += 1

            # Berechne den EHRLICHEN Score: (Anzahl Glückliche / Anzahl Anwesende)
            # 3 von 4 Leuten = 0.75
            manual_score = happy_user_count / len(attendees) if len(attendees) > 0 else 0

            event_entry = event.copy()
            event_entry['attendees'] = ", ".join(attendees)
            event_entry['attendee_count'] = len(attendees)
            event_entry['group_prefs_text'] = " ".join(attendee_prefs_list)
            event_entry['matched_tags'] = ", ".join(matched_tags) if matched_tags else "General"
            
            # Speichere unseren berechneten Score
            event_entry['manual_score'] = manual_score
            
            results.append(event_entry)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # 3. Machine Learning Score (TF-IDF)
    # Dient als Fallback oder Ergänzung
    result_df['event_features'] = (
        result_df['Title'].fillna('') + " " + 
        result_df['Category'].fillna('') + " " +  
        result_df['Description'].fillna('')
    )
    
    try:
        tfidf = TfidfVectorizer(stop_words='english')
        if len(result_df) < 2:
             result_df['match_score'] = result_df['manual_score']
        else:
            tfidf_matrix = tfidf.fit_transform(result_df['event_features'])
            scores = []
            for idx, row in result_df.iterrows():
                # Hier nehmen wir unseren ehrlichen manuellen Score
                # Wenn der > 0 ist (also mind. 1 Person happy), nutzen wir ihn.
                # Wenn er 0 ist (niemand happy), nehmen wir den ML Score als "Vielleicht passt es ja doch irgendwie"-Wert.
                
                if row['manual_score'] > 0:
                    final_score = row['manual_score']
                else:
                    # Fallback auf ML
                    user_vector = tfidf.transform([row['group_prefs_text']])
                    sim = cosine_similarity(user_vector, tfidf_matrix[idx])
                    final_score = sim[0][0]
                
                scores.append(final_score)
                
            result_df['match_score'] = scores
            
    except Exception as e:
        print(f"ML Fehler: {e}")
        # Im Fehlerfall nehmen wir unseren sicheren manuellen Score
        result_df['match_score'] = result_df['manual_score']

    # Sortieren: Zuerst Score, dann Anzahl
    result_df = result_df.sort_values(by=['match_score', 'attendee_count'], ascending=[False, False])
    
    return result_df
