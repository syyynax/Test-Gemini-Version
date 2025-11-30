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
                        else: e_time = pd.to_datetime(str(e_val)).time()
                        
                        start_dt = datetime.combine(current_date, s_time)
                        if e_time < s_time:
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
                    except Exception:
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

def find_best_slots_for_group(events_df, user_busy_map, selected_users, all_user_prefs, min_attendees=2):
    """
    Findet Events und berechnet einen ehrlichen Gruppen-Score.
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
            # 2. Interessen-Check pro Person
            # Wir bauen einen Text aus Titel + Kategorie + Beschreibung
            event_text = (str(event.get('Category', '')) + " " + str(event.get('Description', '')) + " " + str(event['Title'])).lower()
            
            attendee_prefs_list = []
            matched_tags = set()
            
            # Zähler: Wie viele Leute finden das Event gut?
            happy_users_count = 0
            
            for attendee in attendees:
                u_prefs = all_user_prefs.get(attendee, "")
                attendee_prefs_list.append(u_prefs)
                
                user_is_happy = False
                for pref in u_prefs.split(','):
                    clean_pref = pref.strip()
                    # Wenn das Interesse im Event vorkommt
                    if clean_pref and clean_pref.lower() in event_text:
                        matched_tags.add(clean_pref)
                        user_is_happy = True
                
                if user_is_happy:
                    happy_users_count += 1

            # Berechne die Quote: Wie viel Prozent der Gruppe sind glücklich?
            # 2 von 2 Leuten = 1.0 (100%)
            # 1 von 2 Leuten = 0.5 (50%)
            group_happiness_score = happy_users_count / len(attendees) if attendees else 0

            event_entry = event.copy()
            event_entry['attendees'] = ", ".join(attendees)
            event_entry['attendee_count'] = len(attendees)
            event_entry['group_prefs_text'] = " ".join(attendee_prefs_list)
            event_entry['matched_tags'] = ", ".join(matched_tags) if matched_tags else "General"
            
            # Wir speichern diesen "Ehrlichen Score" ab
            event_entry['manual_score'] = group_happiness_score
            
            results.append(event_entry)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # 3. Machine Learning Score (TF-IDF) als "Feinschliff"
    # Wir nutzen TF-IDF weiterhin, um auch unscharfe Treffer zu finden (z.B. ähnliche Wörter),
    # aber wir priorisieren unseren harten Fakten-Check (manual_score).
    result_df['event_features'] = (
        result_df['Title'].fillna('') + " " + 
        result_df['Category'].fillna('') + " " +  
        result_df['Description'].fillna('')
    )
    
    try:
        tfidf = TfidfVectorizer(stop_words='english')
        if len(result_df) < 2:
             # Wenn nur 1 Event da ist, nehmen wir unseren manuellen Score direkt
             result_df['match_score'] = result_df['manual_score']
        else:
            tfidf_matrix = tfidf.fit_transform(result_df['event_features'])
            scores = []
            for idx, row in result_df.iterrows():
                # ML Score berechnen
                user_vector = tfidf.transform([row['group_prefs_text']])
                sim = cosine_similarity(user_vector, tfidf_matrix[idx])
                ml_score = sim[0][0]
                
                # --- INTELLIGENTE MISCHUNG ---
                # Wenn wir einen klaren Keyword-Treffer haben (manual_score > 0),
                # vertrauen wir diesem Score zu 100%.
                # Wenn nicht (manual_score == 0), nutzen wir den ML-Score als Fallback 
                # (vielleicht findet die KI Zusammenhänge, die wir übersehen haben).
                
                if row['manual_score'] > 0:
                    final_score = row['manual_score']
                else:
                    final_score = ml_score
                
                scores.append(final_score)
                
            result_df['match_score'] = scores
            
    except Exception as e:
        print(f"ML Fehler: {e}")
        # Fallback auf unseren manuellen Score
        result_df['match_score'] = result_df['manual_score']

    # Sortieren: Erst Score, dann Anzahl
    result_df = result_df.sort_values(by=['match_score', 'attendee_count'], ascending=[False, False])
    
    return result_df
