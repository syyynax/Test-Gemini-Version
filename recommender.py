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
    total_group_size = len(selected_users) if selected_users else 1

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

            # --- SCORE BERECHNUNG ---
            # Interest Score: Wie viele der ANWESENDEN mögen es?
            interest_score = happy_user_count / len(attendees) if len(attendees) > 0 else 0
            
            # Availability Score: Wie viele der GESAMTGRUPPE können kommen?
            availability_score = len(attendees) / total_group_size if total_group_size > 0 else 0

            event_entry = event.copy()
            event_entry['attendees'] = ", ".join(attendees)
            event_entry['attendee_count'] = len(attendees)
            event_entry['group_prefs_text'] = " ".join(attendee_prefs_list)
            event_entry['matched_tags'] = ", ".join(matched_tags) if matched_tags else "General"
            
            # Speichere die getrennten Scores
            event_entry['interest_score'] = interest_score
            event_entry['availability_score'] = availability_score
            
            results.append(event_entry)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # 3. Machine Learning Score (TF-IDF) als Fallback für Interest
    result_df['event_features'] = (
        result_df['Title'].fillna('') + " " + 
        result_df['Category'].fillna('') + " " +  
        result_df['Description'].fillna('')
    )
    
    try:
        tfidf = TfidfVectorizer(stop_words='english')
        # Berechne ML Score immer, nutze ihn aber nur als Fallback
        if len(result_df) >= 2:
            tfidf_matrix = tfidf.fit_transform(result_df['event_features'])
            ml_scores = []
            for idx, row in result_df.iterrows():
                if row['interest_score'] > 0:
                    ml_scores.append(row['interest_score'])
                else:
                    user_vector = tfidf.transform([row['group_prefs_text']])
                    sim = cosine_similarity(user_vector, tfidf_matrix[idx])
                    ml_scores.append(sim[0][0])
            result_df['final_interest_score'] = ml_scores
        else:
             # Wenn nur 1 Event und wir haben einen manuellen Treffer -> 1.0, sonst 0.5
             val = result_df.iloc[0]['interest_score']
             result_df['final_interest_score'] = val if val > 0 else 0.5
            
    except Exception as e:
        print(f"ML Fehler: {e}")
        result_df['final_interest_score'] = result_df['interest_score']

    # Kombinierter Score für Sortierung (Gewichtet beides)
    result_df['sort_score'] = result_df['availability_score'] + result_df['final_interest_score']

    # Sortieren: Erst nach Gesamt-Score
    result_df = result_df.sort_values(by=['sort_score'], ascending=[False])
    
    return result_df
