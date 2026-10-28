"""SQLite repository with explicit transactions and a versioned initial schema."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError("Unsupported database schema; migration required")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, as_of TEXT NOT NULL, snapshots TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS findings (
                  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                  payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open');
                CREATE TABLE IF NOT EXISTS changes (
                  id TEXT PRIMARY KEY, finding_id TEXT NOT NULL REFERENCES findings(id),
                  proposed TEXT NOT NULL, old_value TEXT NOT NULL, reason TEXT NOT NULL,
                  requested_by TEXT NOT NULL, reviewed_by TEXT,
                  status TEXT NOT NULL DEFAULT 'pending');
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY, change_id TEXT NOT NULL REFERENCES changes(id),
                  actor TEXT NOT NULL, action TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS findings_run ON findings(run_id);
            """)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def encoded(value) -> str:
    return json.dumps(value, sort_keys=True)
