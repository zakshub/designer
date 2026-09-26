"""Transactional local storage. All writes go through the workflow service."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .model import Invalid, NotFound


class Store:
    def __init__(self, path, fixture_mode=False, check_same_thread=True):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10, check_same_thread=check_same_thread)
        self.audit_context = None
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, object_id TEXT NOT NULL,
                revision INTEGER NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
                at TEXT NOT NULL, reason TEXT NOT NULL, body TEXT NOT NULL,
                UNIQUE(object_id, revision));
            CREATE TABLE IF NOT EXISTS applied_outcomes (
                outcome_id TEXT PRIMARY KEY, outcome_revision INTEGER NOT NULL,
                knowledge_id TEXT NOT NULL, at TEXT NOT NULL);
        """)
        mode = "fixture" if fixture_mode else "live"
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('mode', ?)", (mode,))
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1.0.0')")
        if self.db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0] != mode:
            self.db.close()
            raise Invalid("Database mode mismatch; use a separate database for fictional fixtures")
        if self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] != "1.0.0":
            self.db.close()
            raise Invalid("Unsupported database schema version; migration required")
        self.fixture_mode = fixture_mode

    def close(self):
        self.db.close()

    @contextmanager
    def snapshot(self):
        """Keep a sequence of read queries on one committed database snapshot."""
        self.db.execute("BEGIN")
        try:
            yield
        finally:
            self.db.execute("ROLLBACK")

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def all(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT body FROM objects ORDER BY id")]

    def get(self, object_id):
        row = self.db.execute("SELECT body FROM objects WHERE id=?", (object_id,)).fetchone()
        if row is None:
            raise NotFound(f"Unknown object: {object_id}")
        return json.loads(row[0])

    def save(self, obj, action, actor):
        if not self.db.in_transaction:
            raise RuntimeError("Writes require a transaction")
        body = json.dumps(obj, sort_keys=True, allow_nan=False)
        self.db.execute("INSERT INTO objects VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, body=excluded.body",
                        (obj["id"], obj["revision"], body))
        cursor = self.db.execute("INSERT INTO history (object_id,revision,action,actor,at,reason,body) VALUES (?,?,?,?,?,?,?)",
                        (obj["id"], obj["revision"], action, actor, obj["updated_at"], obj["change_reason"], body))
        if self.audit_context:
            context = self.audit_context
            self.db.execute("INSERT INTO api_history_context VALUES(?,?,?,?,?,?)",
                            (cursor.lastrowid, context["user_id"], context["username"], context["role"],
                             context["session_id"], context["request_id"]))

    def history(self, object_id):
        self.get(object_id)
        rows = [{**dict(row), "body": json.loads(row["body"])} for row in self.db.execute(
            "SELECT * FROM history WHERE object_id=? ORDER BY revision", (object_id,))]
        has_auth = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='api_history_context' AND type='table'").fetchone()
        for row in rows:
            context = self.db.execute("SELECT * FROM api_history_context WHERE history_sequence=?", (row["sequence"],)).fetchone() if has_auth else None
            row["authentication"] = {"authenticated": True, "via": "api", **dict(context)} if context else {"authenticated": False, "via": "local-cli"}
        return rows

    def backup(self, destination):
        """Consistent SQLite snapshot, refusing to overwrite any existing path."""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb"):
                pass
        except FileExistsError as exc:
            raise Invalid("Backup destination already exists; choose a new path") from exc
        target = sqlite3.connect(path)
        try:
            self.db.backup(target)
        finally:
            target.close()
        return {"backup": str(path.resolve()), "includes": ["objects", "history", "applied_outcomes", "mode", "schema_version"]}
