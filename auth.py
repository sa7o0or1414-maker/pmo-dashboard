import hashlib
from db import get_conn

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def ensure_hashed_passwords():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, password FROM users")
    users = cur.fetchall()
    for u, p in users:
        if len(p) != 64:
            cur.execute("UPDATE users SET password=? WHERE username=?", (hash_pw(p), u))
    conn.commit()
    conn.close()

def login(username: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, password, role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None
    u, pw_hash, role = row
    if pw_hash == hash_pw(password):
        return {"username": u, "role": role}
    return None

def create_user(username: str, password: str, role: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, hash_pw(password), role)
    )
    conn.commit()
    conn.close()
