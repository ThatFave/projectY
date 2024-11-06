import sqlite3

def create_tables():
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    # Haupttabelle für Benutzerdaten
    c.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT NOT NULL,
        join_date TIMESTAMP NOT NULL,
        message_count INTEGER DEFAULT 0,
        voice_time INTEGER DEFAULT 0,
        last_spotify_song TEXT,
        last_game_played TEXT,
        skipped_song_count INTEGER DEFAULT 0,
        abrupt_game_end_count INTEGER DEFAULT 0,
        total_game_time INTEGER DEFAULT 0
    )
    """)

    # Tabelle für Tages- und Wochentrends
    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_weekly_trends (
        user_id INTEGER PRIMARY KEY,
        date DATE NOT NULL,
        username TEXT NOT NULL,
        messages INTEGER DEFAULT 0,
        voice_time INTEGER DEFAULT 0,
        game_time INTEGER DEFAULT 0,
        skipped_songs INTEGER DEFAULT 0,
        abrupt_games INTEGER DEFAULT 0,
        type TEXT CHECK(type IN ('daily', 'weekly'))
    )
    """)

    # table for history log
    c.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            activity_type TEXT NOT NULL,
            activity_details TEXT,
            artist_name TEXT,
            track_id TEXT
        )
    """)

    conn.commit()
    conn.close()
