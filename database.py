import sqlite3

DB_PATH = "user_database.sqlite"

def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            preferences TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(name, email, preferences):
    """Fügt einen User hinzu oder aktualisiert ihn."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Präferenzen als String speichern (z.B. "Sport,Kultur")
    prefs_str = ",".join(preferences) if isinstance(preferences, list) else preferences
    
    try:
        c.execute("""
            INSERT OR REPLACE INTO users (name, email, preferences)
            VALUES (?, ?, ?)
        """, (name, email, prefs_str))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()

def get_all_users():
    """Holt alle User als Liste von Tupeln (Name, Prefs)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, preferences FROM users")
    rows = c.fetchall()
    conn.close()
    return rows
