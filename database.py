# database.py
import sqlite3
import datetime
import pandas as pd
from config import DB_FILE

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
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
    conn.commit()
    conn.close()

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