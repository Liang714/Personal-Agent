import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from agent import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    source TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_emails (
    message_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def add_task(description: str, source: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (description, source, created_at) VALUES (?, ?, ?)",
            (description, source, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def add_journal_index(entry_date: str, file_path: str, source: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO journal_index (entry_date, file_path, source, created_at) VALUES (?, ?, ?, ?)",
            (entry_date, file_path, source, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def list_open_tasks() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM tasks WHERE done = 0 ORDER BY created_at DESC").fetchall()
