import sqlite3
import os

# Define the path to our database file
DB_PATH = "user_database.sqlite"


def init_db():
    """
    Initializes the database and creates the necessary tables if they don't exist.
    This function establishes the schema for two key entities:
    Users: Stores individual user data and preferences
    Saved Events: Stores events recommended and finalized by the group 
    """
    # Connect SQLite database file. It will be created if it doesn't exist. 
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. User Table
    # This table sotres user profile information crucial for recommendation logic.
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            preferences TEXT
        )
    """)
    
    # 2. Saved Events Table (WITH DETAILS)
    # This table stores the final, selected event from the recommandation process
    # along with their computed match scores and attendee lists. 
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            start_time TEXT,
            end_time TEXT,
            color TEXT,
            category TEXT,
            attendees TEXT,
            match_score REAL,
            location TEXT
        )
    """)
    
    # Commit the changes to finalize table creation 
    conn.commit()
    conn.close()

def add_user(name, email, preferences):
    """
    Adds a new user or updates an existing one based on the email address.
    Upsert funcionality (Update or Insert); if an email exists, user's name and preferences are updated; otherwise a new user is created 
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Convert preferences list to a comma-separated string if needed, which is the storage format 
    prefs_str = ",".join(preferences) if isinstance(preferences, list) else preferences
    
    try:
        if email and email.strip() != "":
            # Check if user already exists using the unique email address
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing = c.fetchone()
            
            if existing:
                # User exists: Perform an update operation 
                c.execute("""
                    UPDATE users 
                    SET name = ?, preferences = ? 
                    WHERE email = ?
                """, (name, prefs_str, email))
                operation = "updated"
            else:
                # User does not exist: Perform an insert operation 
                c.execute("""
                    INSERT INTO users (name, email, preferences)
                    VALUES (?, ?, ?)
                """, (name, email, prefs_str))
                operation = "created"
        else:
            # Handle cases where no email is provided (assigns a unique dummy email)
            import uuid
            dummy_email = f"no_email_{uuid.uuid4()}@local"
            c.execute("""
                INSERT INTO users (name, email, preferences)
                VALUES (?, ?, ?)
            """, (name, dummy_email, prefs_str))
            operation = "created_no_email"

        conn.commit()
        return True, operation
    except Exception as e:
        print(f"Database Error: {e}")
        return False, str(e)
    finally:
        conn.close()

def get_all_users():
    """
    Retrieves all user names and their preference strings from the database.
    Returns: a list of tuples, where each tuple is (name, preferences_string):
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Only fetching name and preferences, as email is typically sensitive/ not needed for recommandation 
    c.execute("SELECT name, preferences FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

# --- EVENT FUNCTIONS (EXTENDED) ---

def add_saved_event(title, start, end, color, category, attendees, match_score, location):
    """
    Saves a selected group event to the database, including all detailed metadata.
    Prevents saving duplicate events.
    Returns: 
        bool: True if event was successfully saved, False otherwise (including duplicates).
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check for exact duplicates (same title and start time) to manipulate data integrity 
        c.execute("SELECT id FROM saved_events WHERE title = ? AND start_time = ?", (title, start))
        if c.fetchone():
            return False # Duplicate found, do not save again
        
        c.execute("""
            INSERT INTO saved_events (title, start_time, end_time, color, category, attendees, match_score, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, start, end, color, category, attendees, match_score, location))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}") 
        return False
    finally:
        conn.close()

def get_saved_events():
    """
    Retrieves all saved events and formats the data into a structure suitable 
    for common calendar display libraries.
    Returns:
        list: A list of dictionnaries, each formatted as calendar event object
    """ 
    conn = sqlite3.connect(DB_PATH)
    # Set the row factory to sqlite3.Rom so columns can be accessed by name (e.g., row[title])
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    
    try:
        c.execute("SELECT * FROM saved_events")
    except Exception:
        # Gracefully handle error if the table hasn't been created yet 
        return []

    rows = []
    for row in c.fetchall():
        # Handle cases where the 'location' column might not exist 
        loc = row['location'] if 'location' in row.keys() else "TBD"

        # Map database fields to a standardized calendar event format 
        event_dict = {
            "title": row['title'],
            "start": row['start_time'],
            "end": row['end_time'],
            "backgroundColor": row['color'],
            "borderColor": row['color'],
            # Use 'extendedProps' to store non-standard metadata for display in toolips/popups
            "extendedProps": {
                "category": row['category'],
                "attendees": row['attendees'],
                "match_score": row['match_score'],
                "location": loc
            }
        }
        rows.append(event_dict)
        
    conn.close()
    return rows

def clear_saved_events():
    """
    Deletes the entire 'saved_events' tale and re-initializes the databse structure.
    This is useful for cleanup, testing or resetting the list of past recommendations.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Use DROP TABLE to permanently remove the table 
    c.execute("DROP TABLE IF EXISTS saved_events") 
    conn.commit()
    conn.close()
    # Call init_db() to recreate the empty table immediately
    init_db()
