import sqlite3
import datetime
import pandas as pd
import threading
from config import DB_FILE

# [CRITICAL UPDATE] Global Lock untuk mencegah "Database Locked" Error
# Ini memastikan hanya 1 thread yang boleh menulis ke DB dalam satu waktu.
db_lock = threading.Lock()

def init_db():
    """Inisialisasi tabel database (hanya dijalankan sekali saat start)."""
    # Tidak perlu lock di sini karena dijalankan di main thread sebelum proses lain mulai
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
    
    # Tabel History Prompt (Prompt Architect)
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
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            c.execute('''
                INSERT INTO history (timestamp, filename, new_filename, title, description, keywords, category, output_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ts, filename, new_filename, title, desc, keywords, category, output_path))
            conn.commit()
        except Exception as e:
            print(f"DB Insert Error: {e}")
        finally:
            conn.close()

def get_history_df():
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        try:
            df = pd.read_sql_query("SELECT * FROM history ORDER BY id DESC", conn)
            return df
        except:
            return pd.DataFrame()
        finally:
            conn.close()

def clear_history():
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM history")
        conn.commit()
        conn.close()

# --- FUNGSI PROMPT HISTORY ---
def add_prompt_history(idea, style, model, result):
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            c.execute('''
                INSERT INTO prompt_history (timestamp, idea, style, model, generated_result)
                VALUES (?, ?, ?, ?, ?)
            ''', (ts, idea, style, model, result))
            conn.commit()
        except Exception as e:
            print(f"DB Prompt Insert Error: {e}")
        finally:
            conn.close()

def get_prompt_history_df():
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        try:
            df = pd.read_sql_query("SELECT * FROM prompt_history ORDER BY id DESC", conn)
            return df
        except:
            return pd.DataFrame()
        finally:
            conn.close()

def clear_prompt_history():
    with db_lock: # <--- PENGAMAN
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM prompt_history")
        conn.commit()
        conn.close()

# [BARU] FITUR DASHBOARD QC: Ambil data history terakhir
def get_recent_history(limit=10):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Agar bisa akses kolom pakai nama (dict-like)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            # Convert sqlite Row to Dict standard
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"DB Fetch Error: {e}")
            return []
        finally:
            conn.close()