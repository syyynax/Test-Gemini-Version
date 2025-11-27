import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

def load_local_events(file_path="events.xlsx"):
    """Lädt Events aus der Excel-Datei."""
    try:
        df = pd.read_excel(file_path)
        # Zeitzonen entfernen für einfacheren Vergleich
        df['Start'] = pd.to_datetime(df['Start']).dt.tz_localize(None)
        df['End'] = pd.to_datetime(df['End']).dt.tz_localize(None)
        return df
    except Exception as e:
        # Fallback Daten für Demo-Zwecke
        data = {
            'Title': ['Fallback: Unisport', 'Fallback: Lernen'],
            'Start': [datetime.now(), datetime.now()],
            'End': [datetime.now(), datetime.now()],
            'Category': ['Sport', 'Education'],
            'Description': ['Notfall Daten', 'Notfall Daten']
        }
        return pd.DataFrame(data)

def check_user_availability(event_start, event_end, user_busy_slots):
    """Prüft Verfügbarkeit eines einzelnen Users."""
    for busy in user_busy_slots:
        b_start = busy['start'].replace(tzinfo=None)
        b_end = busy['end'].replace(tzinfo=None)
        
        # Konflikt bei Überlappung
        if (event_start < b_end) and (event_end > b_start):
            return False 
    return True

def find_best_slots_for_group(events_df, user_busy_map, selected_users, all_user_prefs, min_attendees=2):
    """
    Hauptlogik: Findet Events, bei denen mind. X Leute Zeit haben,
    und berechnet den ML-Score basierend auf deren Interessen.
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
        
        # Nur Events behalten, wo genug Leute können
        if len(attendees) >= min_attendees:
            # 2. Präferenzen NUR der Anwesenden sammeln
            attendee_prefs_text = ""
            for attendee in attendees:
                p_text = all_user_prefs.get(attendee, "")
                attendee_prefs_text += " " + p_text
            
            event_entry = event.copy()
            event_entry['attendees'] = ", ".join(attendees)
            event_entry['attendee_count'] = len(attendees)
            event_entry['group_prefs_text'] = attendee_prefs_text
            results.append(event_entry)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # 3. Machine Learning Score (TF-IDF & Cosine Similarity)
    result_df['event_features'] = result_df['Category'].fillna('') + " " + result_df['Description'].fillna('')
    
    tfidf = TfidfVectorizer(stop_words='english')
    # Falls nur 1 Event da ist, wirft sklearn manchmal Fehler, daher try/except oder Check
    try:
        tfidf_matrix = tfidf.fit_transform(result_df['event_features'])
        
        scores = []
        for idx, row in result_df.iterrows():
            user_vector = tfidf.transform([row['group_prefs_text']])
            sim = cosine_similarity(user_vector, tfidf_matrix[idx])
            scores.append(sim[0][0])
            
        result_df['match_score'] = scores
    except:
        result_df['match_score'] = 0.5 # Fallback bei Fehler

    # Sortieren: Erst Teilnehmerzahl, dann Score
    result_df = result_df.sort_values(by=['attendee_count', 'match_score'], ascending=[False, False])
    
    return result_df
