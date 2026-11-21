import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from config import DATABASE_PATH

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DATABASE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except sqlite3.Error:
        pass
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    preferred_category TEXT DEFAULT 'all',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS read_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    snippet_id TEXT NOT NULL,
                    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES subscribers (user_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscribers_active 
                ON subscribers (is_active)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_user_snippet 
                ON read_history (user_id, snippet_id)
            """)
    finally:
        conn.close()

def add_or_update_subscriber(
    user_id: int, 
    chat_id: int, 
    username: Optional[str] = None, 
    first_name: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Adds a new subscriber or reactivates existing one. Returns True if newly added, False if updated."""
    conn = get_connection(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    uname = str(username) if isinstance(username, str) else None
    fname = str(first_name) if isinstance(first_name, str) else None
    is_new = False
    try:
        with conn:
            cur = conn.execute("SELECT user_id, is_active FROM subscribers WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row is None:
                conn.execute("""
                    INSERT INTO subscribers (user_id, chat_id, username, first_name, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (user_id, chat_id, uname, fname, now, now))
                is_new = True
            else:
                conn.execute("""
                    UPDATE subscribers 
                    SET chat_id = ?, username = ?, first_name = ?, is_active = 1, updated_at = ?
                    WHERE user_id = ?
                """, (chat_id, uname, fname, now, user_id))
    finally:
        conn.close()
    return is_new

def set_subscriber_status(
    user_id: int, 
    is_active: bool, 
    chat_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> bool:
    """Sets active/paused status. If subscriber record doesn't exist yet, creates it."""
    conn = get_connection(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with conn:
            cur = conn.execute("""
                UPDATE subscribers 
                SET is_active = ?, updated_at = ?
                WHERE user_id = ?
            """, (1 if is_active else 0, now, user_id))
            if cur.rowcount == 0 and chat_id is not None:
                conn.execute("""
                    INSERT INTO subscribers (user_id, chat_id, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, chat_id, 1 if is_active else 0, now, now))
                return True
            return cur.rowcount > 0
    finally:
        conn.close()

def set_preferred_category(
    user_id: int, 
    category: str, 
    chat_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> bool:
    """Sets preferred category. If subscriber record doesn't exist yet, creates it."""
    conn = get_connection(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with conn:
            cur = conn.execute("""
                UPDATE subscribers 
                SET preferred_category = ?, updated_at = ?
                WHERE user_id = ?
            """, (category, now, user_id))
            if cur.rowcount == 0 and chat_id is not None:
                conn.execute("""
                    INSERT INTO subscribers (user_id, chat_id, is_active, preferred_category, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                """, (user_id, chat_id, category, now, now))
                return True
            return cur.rowcount > 0
    finally:
        conn.close()

def get_subscriber(user_id: int, db_path: Optional[str] = None) -> Optional[Dict]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM subscribers WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_active_subscribers(db_path: Optional[str] = None) -> List[Dict]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM subscribers WHERE is_active = 1")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def record_delivery(user_id: int, snippet_id: str, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO read_history (user_id, snippet_id)
                VALUES (?, ?)
            """, (user_id, snippet_id))
    finally:
        conn.close()

def get_seen_snippet_ids(user_id: int, db_path: Optional[str] = None) -> Set[str]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT snippet_id FROM read_history WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
        return {r["snippet_id"] for r in rows}
    finally:
        conn.close()

def reset_seen_history(user_id: int, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM read_history WHERE user_id = ?", (user_id,))
    finally:
        conn.close()

def get_subscriber_counts(db_path: Optional[str] = None) -> Dict[str, int]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active
            FROM subscribers
        """)
        row = cur.fetchone()
        total = row["total"] if row and row["total"] is not None else 0
        active = row["active"] if row and row["active"] is not None else 0
        return {"total": total, "active": active}
    finally:
        conn.close()
