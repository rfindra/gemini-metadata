import sqlite3
import datetime
import pandas as pd
from config import DB_FILE

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tabel History Metadata (File)
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            filename TEXT,
            new_filename TEXT,
            title TEXT,
            description TEXT,
            keywords TEXT,
            category TEXT,
            output_path TEXT
        )
    ''')
    # Tabel History Prompt (Baru)
    c.execute('''
        CREATE TABLE IF NOT EXISTS prompt_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            idea TEXT,
            style TEXT,
            model TEXT,
            generated_result TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- FUNGSI METADATA HISTORY ---
def add_history_entry(filename, new_filename, title, desc, keywords, category, output_path):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO history (timestamp, filename, new_filename, title, description, keywords, category, output_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ts, filename, new_filename, title, desc, keywords, category, output_path))
    conn.commit()
    conn.close()

def get_history_df():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM history ORDER BY id DESC", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def clear_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

# --- FUNGSI PROMPT HISTORY (BARU) ---
def add_prompt_history(idea, style, model, result):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO prompt_history (timestamp, idea, style, model, generated_result)
        VALUES (?, ?, ?, ?, ?)
    ''', (ts, idea, style, model, result))
    conn.commit()
    conn.close()

def get_prompt_history_df():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM prompt_history ORDER BY id DESC", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def clear_prompt_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM prompt_history")
    conn.commit()
    conn.close()