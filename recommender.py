# This file contains the core recommendation engine logic for Meetly
# It processes local activity data and combines it with user availability (fetched
# from Google Calendar) and user interest profiles (from the database) 
# to calculate a weighted score for each potential group event. 
# Key components:
# - Data loading: Reads activity ideas from static files (e.g. events.xlsx)
# - Interest matching: Calculates how well an activity's category matches the
# selected group member's preferences.
# - Availability check: Calculates the number of people available for a given time slot
# by cross-referencing against the Google Calendar busy map. 
# - Scoring and ranking: Combines interest and availabiltiy scores to rank the best 
# potential time slots and activities for the entire group 
#
# --- MACHINE LEARNING & LOGIC EXPLANATION ---
# We are not using an external AI service (no API calls).
# Instead, we implemented a "Content-Based Recommender" algorithm ourselves.
#
# How it works:
# 1. Feature Engineering: We combine the Title, Category, and Description of an event into a single text vector.
# 2. TF-IDF Vectorization: We convert this text into mathematical vectors using TF-IDF (Term Frequency-Inverse Document Frequency).
#    This gives more weight to rare, specific words (like "Football") and less to common filler words.
# 3. Cosine Similarity: We calculate the angle (similarity) between the group's interest vector and the event's vector.
#    A value of 1.0 means a perfect match, 0.0 means no similarity.
# ----------------------------------------------------




import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta, time
import os


def load_local_events(file_path="events.xlsx"):
    """
    Loads events from the local excel file. 
    The function handles two main formats:
    Fixed dates: Events with defined 'Start' and 'End' datetimes
    Weekly: Events defined by 'weekday' (0= monday, 6 = sunday) and 'start_time'/'end_time'
    It generates concrete events for the next 30 days.
    """
    generated_events = []
    
    try:
        # Auto-detect file type (.xlsx/.xls for Excel, anything else defaults to CVS)
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        # Normalize column names (lowercase, strip whitespace) to avoid case-sensitivity issues
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        # Check if we have the 'weekly' format (weekday column instead of date)
        if 'weekday' in df.columns and 'event_name' in df.columns:
            today = datetime.now().date()
            
            # iterate through the next 30 days to generate all potential event instances
            for i in range(30):
                current_date = today + timedelta(days=i)
                current_weekday = current_date.weekday() # 0 = Monday, 6 = Sunday
                
                # Filter the source df to find all recurring events scheduled for this specific day 
                days_events = df[df['weekday'] == current_weekday]
                
                for _, row in days_events.iterrows():
                    try:
                        # Parse start and end times robustly (handle strings and time objects)
                        s_val = row['start_time']
                        e_val = row['end_time']
                        
                        # Handle both 'time' objects (from Excel reading) and string representations 
                        if isinstance(s_val, time): s_time = s_val
                        else: s_time = pd.to_datetime(str(s_val)).time()

                        if isinstance(e_val, time): e_time = e_val
                        else: 
                            try: e_time = pd.to_datetime(str(e_val)).time()
                            except: e_time = time(0, 0) # Default endtime if parsing fails
                        
                        # Combine the concrete date with the parsed time 
                        start_dt = datetime.combine(current_date, s_time)
                        
                        # Important!: Handle overnight events (e.g., 22:00 to 02:00 next day)
                        if e_time <= s_time and e_time != time(0,0):
                            # End time is earlier than start time (or equal), so it must end on the next day 
                             end_dt = datetime.combine(current_date + timedelta(days=1), e_time)
                        elif e_time == time(0,0): # Ends exactly at midnight
                            # Handle exact midnight ending: ends on the next day at 00:00:00
                             end_dt = datetime.combine(current_date + timedelta(days=1), e_time)
                            # Standard event: ends on the same day 
                        else:
                            end_dt = datetime.combine(current_date, e_time)

                        # Handle Category column (allow variations like 'kategorie')
                        cat = "General"
                        if 'category' in row: cat = row['category']
                        elif 'kategorie' in row: cat = row['kategorie']

                        raw_loc = row.get('location')
                        
                        # Add the concrete event instance to the list 
                        generated_events.append({
                            'Title': row['event_name'],
                            'Start': start_dt,
                            'End': end_dt,
                            'Category': cat, 
                            'Description': str(row.get('description', '')),
                            'location': raw_loc
                        })
                    except Exception as e:
                        # Skip processing for individual rows that are malformed (e.g., bad time format)
                        continue 
                        
            return pd.DataFrame(generated_events)
        
        # Fallback: If the file uses the old structure with fixed dates
        else:
            # For files with pre-defined 'Start' and 'End' columns, ensure they are datetime objects 
            if 'Start' in df.columns:
                # Convert to datetime and remove any potential timezone information (.dt.tz_localize(None))
                # to allow reliable comparison with busy slots. 
                df['Start'] = pd.to_datetime(df['Start']).dt.tz_localize(None)
            if 'End' in df.columns:
                df['End'] = pd.to_datetime(df['End']).dt.tz_localize(None)
            return df

    except Exception as e:
        print(f"Error loading file: {e}")
        return pd.DataFrame()

# --- Availability Check ---

def check_user_availability(event_start, event_end, user_busy_slots):
    """
    Checks if a single user is free during the event time.
    Function uses the standard interval overlap check
    Returns False if ANY of their busy slots overlap with the event.
    """
    for busy in user_busy_slots:
        # Remove timezone info for comparison (ensures datetimes are timezone-naive)
        b_start = busy['start'].replace(tzinfo=None)
        b_end = busy['end'].replace(tzinfo=None)
        
        # Check for overlap: If the event starts before the busy slot ends AND the event
        # ends after the busy slot starts, there is a conflict 
        if (event_start < b_end) and (event_end > b_start):
            return False # Conflict found, user is NOT available
    return True # No conflict found 

# --- Core recommendation engine (scoring and ranking) ---

def find_best_slots_for_group(events_df, user_busy_map, selected_users, all_user_prefs, min_attendees=1):
    """
    Function calculates two primary scores for each event: 
    1. Availability Score: How many of the total group can attend (0.0 to 1.0)
    2. Interest Score: How well the event matches the attendees preferences (0.0 to 1.0)
    It the combines these two into a final 'sort_score' for ranking 
    """
    if events_df.empty:
        return pd.DataFrame()

    results = []
    total_group_size = len(selected_users) if selected_users else 1

    for _, event in events_df.iterrows():
        attendees = []
        
        # 1. Availability Check: Who is free?
        for user in selected_users:
            busy_slots = user_busy_map.get(user, [])
            if check_user_availability(event['Start'], event['End'], busy_slots):
                attendees.append(user) # User is free
        
        # Only process events where enough people are free
        # Skip the event if it doesn't meet the minimum attendance thershold
        if len(attendees) >= min_attendees:
            
            # 2. Interest Analysis (Detail Check PER PERSON)
            attendee_prefs_list = []
            matched_tags = set()
            
            # Create a searchable text string from the event's metadata 
            event_text = (str(event.get('Category', '')) + " " + str(event.get('Description', '')) + " " + str(event['Title'])).lower()
            
            # Counter for happy users
            happy_user_count = 0
            
            for attendee in attendees:
                u_prefs = all_user_prefs.get(attendee, "")
                attendee_prefs_list.append(u_prefs)
                
                # Check if THIS user likes the event
                user_likes_event = False
                # Iterate through user's preference keywords (split by comma)
                for pref in u_prefs.split(','):
                    clean_pref = pref.strip()
                    # Check for direct keyword match (e.g., "Sport" in event text)
                    if clean_pref and clean_pref.lower() in event_text:
                        matched_tags.add(clean_pref)
                        user_likes_event = True
                        # Optimization: once a match is found for a user, stop checking their other preferences
                
                if user_likes_event:
                    happy_user_count += 1

            # --- SCORE CALCULATION ---
            
            # Interest Score: What percentage of the ATTENDEES like this event?
            # Example: If 2 people go, and 1 likes it -> 50% (0.5)
            interest_score = happy_user_count / len(attendees) if len(attendees) > 0 else 0
            
            # Availability Score: What percentage of the TOTAL GROUP can make it?
            # Example: If 3 out of 4 people are free -> 75% (0.75)
            availability_score = len(attendees) / total_group_size if total_group_size > 0 else 0

            # Store computed metrics
            event_entry = event.copy()
            event_entry['attendees'] = ", ".join(attendees)
            event_entry['attendee_count'] = len(attendees)
            event_entry['group_prefs_text'] = " ".join(attendee_prefs_list)
            event_entry['matched_tags'] = ", ".join(matched_tags) if matched_tags else "General"
            
            # Save the separated scores
            event_entry['interest_score'] = interest_score
            event_entry['availability_score'] = availability_score
            
            results.append(event_entry)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # 3. Machine Learning Score (TF-IDF) as Fallback
    # We use TF-IDF to find matches even if exact keywords are missing,
    # but we prioritize our manual 'interest_score' if it found direct hits.

    # Text corpus for ML training: combine all descriptive fields 
    result_df['event_features'] = (
        result_df['Title'].fillna('') + " " + 
        result_df['Category'].fillna('') + " " +  
        result_df['Description'].fillna('')
    )
    
    try:
        tfidf = TfidfVectorizer(stop_words='english')
        
        # TF-IDF needs at least 2 documents to work effectively
        if len(result_df) >= 2:
            # Train the vectorizer on all events
            tfidf_matrix = tfidf.fit_transform(result_df['event_features'])
            
            ml_scores = []
            for idx, row in result_df.iterrows():
                # If we already have a manual hit (>0), trust it.
                if row['interest_score'] > 0:
                    ml_scores.append(row['interest_score'])
                # If no manual match, use the semantic similarity score from TF-IDF
                else:
                    # Transform the group's combined preferences into a vector 
                    user_vector = tfidf.transform([row['group_prefs_text']])
                    # Cosine similarity measures the angular distance (similarity) between the user vector and the event vector 
                    sim = cosine_similarity(user_vector, tfidf_matrix[idx])
                    ml_scores.append(sim[0][0])
            
            result_df['final_interest_score'] = ml_scores
        else:
             # Fallback for single event case: trust manual score, otherwise default to a neutral score (0.5)
             val = result_df.iloc[0]['interest_score']
             result_df['final_interest_score'] = val if val > 0 else 0.5
            
    except Exception as e:
        print(f"ML Error: {e}") 
        # If the ML process fails unexpectedly, fall back entirely to the manual score
        result_df['final_interest_score'] = result_df['interest_score']

    # 4. Ranking and Sorting
    # We create a combined score to sort the best options to the top.
    # A score of 2.0 means 100% attendance and 100% interest match
    # Both availability and interest are weighted equally here.
    result_df['sort_score'] = result_df['availability_score'] + result_df['final_interest_score']

    # Sort the results so the highest-scoring events (best fit) appear at the top 
    result_df = result_df.sort_values(by=['sort_score'], ascending=[False])
    
    return result_df
