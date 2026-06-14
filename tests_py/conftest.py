import sqlite3
import pytest

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  INTEGER NOT NULL,
    ended_at    INTEGER,
    file        TEXT,
    language    TEXT
);
CREATE TABLE IF NOT EXISTS keystrokes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    ts          INTEGER NOT NULL,
    event_type  TEXT NOT NULL,
    char        TEXT,
    is_delete   INTEGER NOT NULL DEFAULT 0,
    context     TEXT,
    line        INTEGER,
    col         INTEGER
);
CREATE TABLE IF NOT EXISTS pauses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    ts          INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bursts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    ts          INTEGER NOT NULL,
    char_count  INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    wpm         REAL NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    context     TEXT
);
"""

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    yield conn
    conn.close()
