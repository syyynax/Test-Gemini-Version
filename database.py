import sqlite3

# Define the path to our database file
DB_PATH = "user_database.sqlite"

def init_db():
    """Initializes the database and creates the necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. User Table
    # Stores user profiles including name, email (used as a unique ID), and their preferences.
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            preferences TEXT
        )
    """)
    
    # 2. Saved Events Table (WITH DETAILS)
    # Stores group events that users have selected to save to the shared calendar.
    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            start_time TEXT,
            end_time TEXT,
            color TEXT,
            category TEXT,
            attendees TEXT,
            match_score REAL
            location TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def add_user(name, email, preferences):
    """
    Adds a new user or updates an existing one based on the email address.
    Returns: (Success Boolean, Operation Message)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Convert the list of preferences into a single comma-separated string for storage
    prefs_str = ",".join(preferences) if isinstance(preferences, list) else preferences
    
    try:
        # Check if the email already exists to decide whether to INSERT or UPDATE
        if email and email.strip() != "":
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing = c.fetchone()
            
            if existing:
                # Update existing user
                c.execute("""
                    UPDATE users 
                    SET name = ?, preferences = ? 
                    WHERE email = ?
                """, (name, prefs_str, email))
                operation = "updated"
            else:
                # Insert new user
                c.execute("""
                    INSERT INTO users (name, email, preferences)
                    VALUES (?, ?, ?)
                """, (name, email, prefs_str))
                operation = "created"
        else:
            # Fallback: If no email is provided, create a dummy email to satisfy the UNIQUE constraint
            # (Note: In our current UI, email is required, so this is just a safety net)
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
    """Fetches all users from the database to display them in the UI."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, preferences FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

# --- EVENT FUNCTIONS (EXTENDED) ---

def add_saved_event(title, start, end, color, category, attendees, match_score, location):
    """
    Saves a selected group event to the database, including all detailed metadata.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Prevent duplicates: Check if an event with the same title and start time already exists
        c.execute("SELECT id FROM saved_events WHERE title = ? AND start_time = ?", (title, start))
        if c.fetchone():
            return False # Event already exists, do nothing
            
        c.execute("""
            INSERT INTO saved_events (title, start_time, end_time, color, category, attendees, match_score, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
    Retrieves all saved events and formats them for the frontend calendar component.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Allows us to access columns by name (e.g., row['title'])
    c = conn.cursor()
    
    # Fetch all columns
    c.execute("SELECT * FROM saved_events")
    rows = []
    for row in c.fetchall():
        # Build a dictionary formatted for the FullCalendar component
        # We store additional details (category, attendees, score) in 'extendedProps'
        event_dict = {
            "title": row['title'],
            "start": row['start_time'],
            "end": row['end_time'],
            "backgroundColor": row['color'],
            "borderColor": row['color'],
            "extendedProps": {
                "category": row['category'],
                "attendees": row['attendees'],
                "match_score": row['match_score'],
                "location": row['location']
            }
        }
        rows.append(event_dict)
        
    conn.close()
    return rows

def clear_saved_events():
    """Deletes all saved events from the database (Reset functionality)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM saved_events")
    conn.commit()
    conn.close()
    c = conn.cursor()
    c.execute("DELETE FROM saved_events")
    conn.commit()
    conn.close()
