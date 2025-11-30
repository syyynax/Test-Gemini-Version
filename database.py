import sqlite3
import os

# Define the path to our database file
DB_PATH = "user_database.sqlite"

def init_db():
    """Initializes the database and creates the necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. User Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            preferences TEXT
        )
    """)
    
    # 2. Saved Events Table (WITH DETAILS)
    # KORREKTUR: Komma vor 'location TEXT' hinzugefügt
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
    
    conn.commit()
    conn.close()

def add_user(name, email, preferences):
    """
    Adds a new user or updates an existing one based on the email address.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    prefs_str = ",".join(preferences) if isinstance(preferences, list) else preferences
    
    try:
        if email and email.strip() != "":
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing = c.fetchone()
            
            if existing:
                c.execute("""
                    UPDATE users 
                    SET name = ?, preferences = ? 
                    WHERE email = ?
                """, (name, prefs_str, email))
                operation = "updated"
            else:
                c.execute("""
                    INSERT INTO users (name, email, preferences)
                    VALUES (?, ?, ?)
                """, (name, email, prefs_str))
                operation = "created"
        else:
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
        # Prevent duplicates
        c.execute("SELECT id FROM saved_events WHERE title = ? AND start_time = ?", (title, start))
        if c.fetchone():
            return False 
            
        # KORREKTUR: Hier waren nur 7 Fragezeichen, es müssen aber 8 sein!
        c.execute("""
            INSERT INTO saved_events (title, start_time, end_time, color, category, attendees, match_score, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, start, end, color, category, attendees, match_score, location))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}") # Diesen Fehler hast du vorher nicht gesehen
        return False
    finally:
        conn.close()

def get_saved_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    
    # Fehler abfangen, falls Tabelle noch alt ist
    try:
        c.execute("SELECT * FROM saved_events")
    except Exception:
        return []

    rows = []
    for row in c.fetchall():
        # Fallback, falls 'location' in einer alten Zeile leer ist
        loc = row['location'] if 'location' in row.keys() else "TBD"

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
                "location": loc
            }
        }
        rows.append(event_dict)
        
    conn.close()
    return rows

def clear_saved_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS saved_events") # Besser DROP nutzen um Struktur neu zu laden
    conn.commit()
    conn.close()
    init_db()
