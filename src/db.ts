import Database from 'better-sqlite3';
import * as path from 'path';
import * as os from 'os';

const DB_PATH = path.join(os.homedir(), '.soul', 'soul.db');

let _db: Database.Database | undefined;

export function db(): Database.Database {
  if (!_db) {
    const fs = require('fs');
    fs.mkdirSync(path.dirname(DB_PATH), { recursive: true, mode: 0o700 });
    try { fs.chmodSync(path.dirname(DB_PATH), 0o700); } catch {}
    _db = new Database(DB_PATH);
    try { fs.chmodSync(DB_PATH, 0o600); } catch {}
    _db.pragma('journal_mode = WAL');
    for (const suffix of ['-wal', '-shm']) {
      try { fs.chmodSync(DB_PATH + suffix, 0o600); } catch {}
    }
    migrate(_db);
  }
  return _db;
}

function migrate(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS sessions (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      started_at  INTEGER NOT NULL,
      ended_at    INTEGER,
      file        TEXT,
      language    TEXT
    );

    CREATE TABLE IF NOT EXISTS keystrokes (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id  INTEGER NOT NULL REFERENCES sessions(id),
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
      session_id  INTEGER NOT NULL REFERENCES sessions(id),
      ts          INTEGER NOT NULL,
      duration_ms INTEGER NOT NULL,
      before_ctx  TEXT,
      after_ctx   TEXT
    );

    CREATE TABLE IF NOT EXISTS bursts (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id  INTEGER NOT NULL REFERENCES sessions(id),
      ts          INTEGER NOT NULL,
      char_count  INTEGER NOT NULL,
      duration_ms INTEGER NOT NULL,
      wpm         REAL NOT NULL,
      error_count INTEGER NOT NULL DEFAULT 0,
      context     TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_keystrokes_session ON keystrokes(session_id);
    CREATE INDEX IF NOT EXISTS idx_pauses_session ON pauses(session_id);
    CREATE INDEX IF NOT EXISTS idx_bursts_session ON bursts(session_id);
  `);
}
