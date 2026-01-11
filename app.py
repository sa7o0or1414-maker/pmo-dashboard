import sqlite3
from pathlib import Path

DB_PATH = Path("pmo.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS fact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_date TEXT,
        municipality TEXT,
        entity TEXT,
        project TEXT,
        status TEXT,
        budget REAL,
        progress REAL
    )
    """)

    conn.commit()
    conn.close()

def upsert_default_admin():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )
    conn.commit()
    conn.close()

def replace_week_data(df, week_date):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM fact WHERE week_date = ?", (week_date,))
    conn.commit()

    rows = df.to_dict(orient="records")
    cur.executemany("""
        INSERT INTO fact (week_date, municipality, entity, project, status, budget, progress)
        VALUES (:week_date, :municipality, :entity, :project, :status, :budget, :progress)
    """, rows)

    conn.commit()
    conn.close()
