"""SQLite repository with explicit transactions and a versioned initial schema."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 2


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise RuntimeError("Unsupported database schema; migration required")
            schema = """
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
            """
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
            extension = """
                CREATE TABLE IF NOT EXISTS run_context (
                  run_id TEXT PRIMARY KEY REFERENCES runs(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS case_work (
                  finding_id TEXT PRIMARY KEY REFERENCES findings(id), payload TEXT NOT NULL,
                  version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS batches (
                  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                  payload TEXT NOT NULL, status TEXT NOT NULL, requested_by TEXT NOT NULL,
                  reviewed_by TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS lab_events (
                  id INTEGER PRIMARY KEY, object_id TEXT NOT NULL, actor TEXT NOT NULL,
                  action TEXT NOT NULL, detail TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS documents (
                  kind TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
                  payload TEXT NOT NULL, actor TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY(kind,id,version));
                CREATE TABLE IF NOT EXISTS test_runs (
                  id TEXT PRIMARY KEY, release TEXT NOT NULL, payload TEXT NOT NULL,
                  actor TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS lab_object_events ON lab_events(object_id,id);
            """
            for statement in extension.split(";"):
                if statement.strip():
                    db.execute(statement)
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
