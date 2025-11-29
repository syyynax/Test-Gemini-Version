import sqlite3

DB_PATH = "user_database.sqlite"

def init_db():
    """Initialisiert die Datenbank."""
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
    """
    Fügt User hinzu. 
    WICHTIG: Identifiziert User über die E-Mail.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    prefs_str = ",".join(preferences) if isinstance(preferences, list) else preferences
    
    try:
        # 1. Prüfen: Gibt es diese E-Mail schon?
        if email and email.strip() != "":
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            existing = c.fetchone()
            
            if existing:
                # UPDATE: User existiert -> Aktualisieren
                c.execute("""
                    UPDATE users 
                    SET name = ?, preferences = ? 
                    WHERE email = ?
                """, (name, prefs_str, email))
                operation = "updated"
            else:
                # INSERT: User neu -> Anlegen
                c.execute("""
                    INSERT INTO users (name, email, preferences)
                    VALUES (?, ?, ?)
                """, (name, email, prefs_str))
                operation = "created"
        else:
            # Fallback: Keine Email angegeben -> Immer neu anlegen (mit Fake-Email für Unique Constraint)
            # Wir hängen einen Zeitstempel oder Random an, damit es unique bleibt
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
