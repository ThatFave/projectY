import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from helper import create_tables

# Discord-Bot initialisieren
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.messages = True
intents.voice_states = True

# load .env
load_dotenv()

bot = commands.Bot(command_prefix="!", intents=intents)

# init db
create_tables()

# Zwischenspeicher für laufende Aktivitäten
user_activities = {}
user_voice_states = {}

# Event: Nachricht gesendet
@bot.event
async def on_message(message):
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    if message.author == bot.user:
        return

    today = datetime.now().date()

    # Update daily activity
    c.execute("""
        INSERT INTO daily_weekly_trends (date, user_id, username, messages, voice_time, game_time, skipped_songs, abrupt_games, type)
        VALUES (?, ?, ?, 1, 0, 0, 0, 0, 'daily')
        ON CONFLICT(date, user_id, type)
        DO UPDATE SET messages = messages + 1;
    """, (today, message.author.id, message.author.name))

    # Update user activity
    c.execute("""
        INSERT INTO activity (user_id, username, join_date, message_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id) 
        DO UPDATE SET message_count = message_count + 1;
    """, (message.author.id, message.author.name, message.created_at))
    conn.commit()

    print(f"{message.author}: {message.content} in {message.channel} at {message.created_at}")

    await bot.process_commands(message)

# Event: Voice-State-Änderung
@bot.event
async def on_voice_state_update(member, before, after):
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    voice_times = {}
    current_time = datetime.now()

    if before.channel is None and after.channel is not None:
        voice_times[member.id] = current_time
    elif before.channel is not None and after.channel is None:
        join_time = voice_times.pop(member.id, None)
        if join_time:
            time_spent = current_time - join_time
            print(f'{member.name} spent {time_spent} in {before.channel}')
            c.execute("BEGIN; UPDATE activity SET voice_time = voice_time + ? WHERE user_id = ?; COMMIT;", (time_spent, member.id))
            conn.commit()

# Hintergrund-Task: Spiel-Tracking aktualisieren
@bot.event
async def on_presence_update(before, after):
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()
    user_id = after.id
    username = after.name
    timestamp = datetime.now().isoformat()  # Convert datetime to ISO format

    # Insert a new row for a user in the main activity table if they don't exist
    c.execute("""
        INSERT INTO activity (user_id, username, join_date)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO NOTHING
    """, (user_id, username, timestamp))
    conn.commit()

    # Check if the activity changed and log it
    if before.activity != after.activity:
        if after.activity:
            if after.activity.type == discord.ActivityType.playing:
                # Log game start in activity_log
                game_name = after.activity.name
                c.execute("""
                    INSERT INTO activity_log (user_id, username, timestamp, activity_type, activity_details)
                    VALUES (?, ?, ?, 'Game Started', ?)
                """, (user_id, username, timestamp, game_name))
                print(f"{username} started playing {game_name}")

            elif after.activity.type == discord.ActivityType.listening and after.activity.name == 'Spotify':
                # Extract details about the Spotify activity
                song_name = after.activity.title
                artist_name = after.activity.artist if hasattr(after.activity, 'artist') else None
                track_id = after.activity.track_id if hasattr(after.activity, 'track_id') else None
                
                # Log Spotify song start in activity_log with artist and track ID
                c.execute("""
                    INSERT INTO activity_log (user_id, username, timestamp, activity_type, activity_details, artist_name, track_id)
                    VALUES (?, ?, ?, 'Spotify Song Started', ?, ?, ?)
                """, (user_id, username, timestamp, song_name, artist_name, track_id))
                print(f"{username} is listening to {song_name} by {artist_name} (Track ID: {track_id})")

        else:
            # User stopped an activity
            if before.activity and before.activity.type == discord.ActivityType.playing:
                # Log game end in activity_log
                game_name = before.activity.name
                c.execute("""
                    INSERT INTO activity_log (user_id, username, timestamp, activity_type, activity_details)
                    VALUES (?, ?, ?, 'Game Stopped', ?)
                """, (user_id, username, timestamp, game_name))
                print(f"{username} stopped playing {game_name}")

    conn.commit()
    conn.close()

@tasks.loop(hours=24)
async def daily_update():
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    # Use ISO format for the date
    today = datetime.now().date().isoformat()  # Convert the date to a string format
    for guild in bot.guilds:
        for member in guild.members:
            c.execute("""
                INSERT INTO daily_weekly_trends (date, user_id, messages, voice_time, game_time, skipped_songs, abrupt_games, type)
                SELECT ?, user_id, message_count, voice_time, total_game_time, skipped_song_count, abrupt_game_end_count, 'daily'
                FROM activity
                WHERE user_id = ?;
            """, (today, member.id))
            conn.commit()

@tasks.loop(hours=168)  # Wöchentlich
async def weekly_update():
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    # Calculate the start of the week and convert to ISO format
    week_start = (datetime.now().date() - timedelta(days=datetime.now().weekday())).isoformat()  # Monday of this week
    for guild in bot.guilds:
        for member in guild.members:
            c.execute("""
                INSERT INTO daily_weekly_trends (date, user_id, messages, voice_time, game_time, skipped_songs, abrupt_games, type)
                SELECT ?, user_id, message_count, voice_time, total_game_time, skipped_song_count, abrupt_game_end_count, 'weekly'
                FROM activity
                WHERE user_id = ?;
            """, (week_start, member.id))
            conn.commit()

# Command: Aktivitätsdaten zurücksetzen (nur für Admins)
@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def reset_activity(ctx, member: discord.Member):
    # Verbindung zur SQLite-Datenbank herstellen
    conn = sqlite3.connect("user_activity.db")
    c = conn.cursor()

    c.execute("BEGIN; DELETE FROM activity WHERE user_id = ?; COMMIT;", (member.id,))
    conn.commit()
    await ctx.send(f"Aktivitätsdaten von {member.name} wurden zurückgesetzt.")

# Command: Hilfe anzeigen
@bot.command(name="helpp")
async def help_command(ctx):
    help_text = """```markdown
    !help - Zeigt diese Hilfe an.
    !reset @User - Setzt die Aktivitätsdaten eines bestimmten Benutzers zurück.
    ```
    """
    await ctx.send(help_text)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} ist online.')
    daily_update.start()
    weekly_update.start()

# Bot starten
bot.run(os.getenv('DISCORD_TOKEN'))
