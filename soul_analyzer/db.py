import sqlite3
from pathlib import Path

DB_PATH = Path.home() / '.soul' / 'soul.db'


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"soul.db not found at {db_path}. Run a recording session first.")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
