import sqlite3
import datetime
import pandas as pd
import threading
from config import DB_FILE

# Global Lock untuk keamanan thread
db_lock = threading.Lock()

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

def add_history_entry(filename, new_filename, title, desc, keywords, category, output_path):
    with db_lock:
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

# [BARU] Fungsi Update Data setelah Regenerate
def update_history_entry(old_filename_in_db, new_filename, title, desc, keywords):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            # Update data berdasarkan nama file yang tersimpan di DB sebelumnya
            c.execute('''
                UPDATE history 
                SET new_filename = ?, title = ?, description = ?, keywords = ?
                WHERE new_filename = ?
            ''', (new_filename, title, desc, keywords, old_filename_in_db))
            conn.commit()
        except Exception as e:
            print(f"DB Update Error: {e}")
        finally:
            conn.close()

# [BARU] Ambil Data dengan Pagination & Search (Untuk Gallery Minimalis)
def get_paginated_history(page=1, per_page=12, search_query=""):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Agar bisa akses kolom by name
        offset = (page - 1) * per_page
        
        try:
            cursor = conn.cursor()
            
            if search_query:
                q = f"%{search_query}%"
                # Hitung total untuk pagination
                cursor.execute("SELECT COUNT(*) FROM history WHERE new_filename LIKE ? OR title LIKE ?", (q, q))
                total_items = cursor.fetchone()[0]
                
                # Ambil data
                cursor.execute("SELECT * FROM history WHERE new_filename LIKE ? OR title LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?", (q, q, per_page, offset))
            else:
                cursor.execute("SELECT COUNT(*) FROM history")
                total_items = cursor.fetchone()[0]
                
                cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset))
            
            rows = cursor.fetchall()
            return rows, total_items
        except Exception as e:
            print(f"DB Fetch Error: {e}")
            return [], 0
        finally:
            conn.close()

def get_history_df():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        try:
            df = pd.read_sql_query("SELECT * FROM history ORDER BY id DESC", conn)
            return df
        except:
            return pd.DataFrame()
        finally:
            conn.close()

def clear_history():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM history")
        conn.commit()
        conn.close()

def add_prompt_history(idea, style, model, result):
    with db_lock:
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
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        try:
            df = pd.read_sql_query("SELECT * FROM prompt_history ORDER BY id DESC", conn)
            return df
        except:
            return pd.DataFrame()
        finally:
            conn.close()

def clear_prompt_history():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM prompt_history")
        conn.commit()
        conn.close()

def get_recent_history(limit=5):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return rows
        except: return []
        finally: conn.close()