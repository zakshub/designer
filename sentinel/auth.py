"""Local accounts, opaque sessions, throttling, and additive auth migration."""

import hashlib
import hmac
import re
import secrets
import time
import uuid
import json

from .model import Invalid

ROLES = {"viewer": 0, "editor": 1, "reviewer": 2, "admin": 3}
ITERATIONS = 600_000
SESSION_SECONDS = 3600


class AuthError(Invalid):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def migrate_auth(store):
    """Add tables atomically without altering knowledge or review state."""
    with store.transaction():
        row = store.db.execute("SELECT value FROM metadata WHERE key='auth_schema_version'").fetchone()
        if row and row[0] != "1":
            raise Invalid("Unsupported authentication schema version")
        statements = [
            """CREATE TABLE IF NOT EXISTS api_users (
                id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('viewer','editor','reviewer','admin')),
                active INTEGER NOT NULL CHECK(active IN (0,1)), password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS api_sessions (
                id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL REFERENCES api_users(id), created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS api_login_limits (
                key TEXT PRIMARY KEY, started_at INTEGER NOT NULL, failures INTEGER NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS api_security_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT,
                action TEXT NOT NULL, at INTEGER NOT NULL, request_id TEXT NOT NULL,
                details TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS api_history_context (
                history_sequence INTEGER PRIMARY KEY REFERENCES history(sequence),
                user_id TEXT NOT NULL REFERENCES api_users(id), username TEXT NOT NULL,
                role TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES api_sessions(id),
                request_id TEXT NOT NULL)""",
            "CREATE INDEX IF NOT EXISTS api_session_user ON api_sessions(user_id)",
        ]
        for statement in statements:
            store.db.execute(statement)
        store.db.execute("INSERT OR IGNORE INTO metadata VALUES ('auth_schema_version', '1')")


def check_password_policy(password):
    if not isinstance(password, str) or not 15 <= len(password) <= 128 or not password.strip():
        raise Invalid("Use a password of 15 to 128 characters")


def password_hash(password):
    check_password_policy(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def password_matches(password, stored):
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def public_user(row):
    return {"id": row["id"], "username": row["username"], "role": row["role"],
            "active": bool(row["active"]), "created_at": row["created_at"]}


class Auth:
    def __init__(self, store, clock=time.time):
        self.store, self.db, self.clock = store, store.db, clock

    def event(self, actor_id, action, request_id, details=None):
        self.db.execute("INSERT INTO api_security_events(actor_id,action,at,request_id,details) VALUES(?,?,?,?,?)",
                        (actor_id, action, int(self.clock()), request_id, json.dumps(details or {})))

    def create_user(self, username, password, role, actor_id=None, request_id="local-bootstrap", bootstrap=False, reason="Account provisioning"):
        if not isinstance(username, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}", username) or role not in ROLES:
            raise Invalid("Use a lowercase username of 3-64 characters and a valid role")
        encoded = password_hash(password)
        with self.store.transaction():
            if bootstrap:
                if role != "admin" or self.db.execute("SELECT COUNT(*) FROM api_users").fetchone()[0]:
                    raise AuthError(409, "bootstrap_closed", "Bootstrap is available only before the first account exists")
            elif actor_id is None:
                raise AuthError(403, "forbidden", "An administrator is required")
            else:
                self.require_admin(actor_id)
            if self.db.execute("SELECT 1 FROM api_users WHERE username=?", (username,)).fetchone():
                raise AuthError(409, "user_exists", "Username already exists")
            user_id = uuid.uuid4().hex
            self.db.execute("INSERT INTO api_users VALUES(?,?,?,?,?,?)", (user_id, username, role, 1, encoded, int(self.clock())))
            self.event(actor_id, "bootstrap" if bootstrap else "user-created", request_id, {"target_id": user_id, "role": role, "reason": reason})
            return self.get_user(user_id)

    def get_user(self, user_id):
        row = self.db.execute("SELECT * FROM api_users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise AuthError(404, "not_found", "User not found")
        return public_user(row)

    def require_admin(self, user_id):
        user = self.get_user(user_id)
        if user["role"] != "admin" or not user["active"]:
            raise AuthError(403, "forbidden", "An active administrator is required")

    def login(self, username, password, client, request_id):
        now = int(self.clock())
        keys = [("account:" + hashlib.sha256(username.encode()).hexdigest(), 5),
                ("client:" + hashlib.sha256(client.encode()).hexdigest(), 30)]
        error, result = None, None
        # Failure counters must commit even when authentication fails.
        with self.store.transaction():
            self.db.execute("DELETE FROM api_login_limits WHERE started_at <= ?", (now - 300,))
            limited = any((row := self.db.execute("SELECT failures FROM api_login_limits WHERE key=?", (key,)).fetchone())
                          and row[0] >= threshold for key, threshold in keys)
            if limited:
                self.event(None, "login-throttled", request_id)
                error = AuthError(429, "login_throttled", "Too many login attempts; retry after five minutes")
            else:
                row = self.db.execute("SELECT * FROM api_users WHERE username=?", (username,)).fetchone()
                if row:
                    valid = password_matches(password, row["password_hash"]) and bool(row["active"])
                else:
                    # Comparable password work for unknown accounts; this is not a credential.
                    hashlib.pbkdf2_hmac("sha256", password.encode(), b"sentinel-timing-pad", ITERATIONS)
                    valid = False
                if not valid:
                    for key, _ in keys:
                        self.db.execute("INSERT INTO api_login_limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET failures=failures+1", (key, now))
                    self.event(row["id"] if row else None, "login-failed", request_id)
                    error = AuthError(401, "invalid_credentials", "Invalid credentials")
                else:
                    self.db.execute("DELETE FROM api_login_limits WHERE key=?", (keys[0][0],))
                    token, session_id = secrets.token_urlsafe(32), uuid.uuid4().hex
                    self.db.execute("INSERT INTO api_sessions VALUES(?,?,?,?,?,0)",
                                    (session_id, hashlib.sha256(token.encode()).hexdigest(), row["id"], now, now + SESSION_SECONDS))
                    self.event(row["id"], "login", request_id, {"session_id": session_id})
                    result = {"access_token": token, "token_type": "bearer", "expires_in": SESSION_SECONDS,
                              "expires_at": now + SESSION_SECONDS, "user": public_user(row)}
        if error:
            raise error
        return result

    def authenticate(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise AuthError(401, "unauthorized", "A valid bearer session is required")
        row = self.db.execute("""SELECT u.*, s.id AS session_id FROM api_sessions s
            JOIN api_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.revoked=0
            AND s.expires_at>? AND u.active=1""", (hashlib.sha256(token.encode()).hexdigest(), int(self.clock()))).fetchone()
        if not row:
            raise AuthError(401, "unauthorized", "Session is expired, revoked or invalid")
        return {**public_user(row), "session_id": row["session_id"]}

    def logout(self, principal, request_id):
        with self.store.transaction():
            self.db.execute("UPDATE api_sessions SET revoked=1 WHERE id=?", (principal["session_id"],))
            self.event(principal["id"], "logout", request_id, {"session_id": principal["session_id"]})

    def update_user(self, user_id, role, active, actor_id, request_id, reason):
        with self.store.transaction():
            self.require_admin(actor_id)
            user = self.get_user(user_id)
            role = user["role"] if role is None else role
            active = user["active"] if active is None else active
            if role not in ROLES or type(active) is not bool:
                raise Invalid("Invalid role or active state")
            if user["active"] and user["role"] == "admin" and (not active or role != "admin"):
                count = self.db.execute("SELECT COUNT(*) FROM api_users WHERE active=1 AND role='admin'").fetchone()[0]
                if count <= 1:
                    raise AuthError(409, "last_admin", "The last active administrator must remain available")
            self.db.execute("UPDATE api_users SET role=?,active=? WHERE id=?", (role, int(active), user_id))
            self.db.execute("UPDATE api_sessions SET revoked=1 WHERE user_id=?", (user_id,))
            self.event(actor_id, "user-updated", request_id, {"target_id": user_id, "role": role, "active": active, "reason": reason})
            return self.get_user(user_id)

    def change_password(self, principal, current_password, new_password, request_id):
        encoded = password_hash(new_password)
        with self.store.transaction():
            row = self.db.execute("SELECT password_hash FROM api_users WHERE id=?", (principal["id"],)).fetchone()
            if not row or not password_matches(current_password, row[0]):
                raise AuthError(401, "invalid_credentials", "Invalid credentials")
            self.db.execute("UPDATE api_users SET password_hash=? WHERE id=?", (encoded, principal["id"]))
            self.db.execute("UPDATE api_sessions SET revoked=1 WHERE user_id=?", (principal["id"],))
            self.event(principal["id"], "password-changed", request_id)

    def reset_password(self, user_id, new_password, actor_id, request_id, reason):
        encoded = password_hash(new_password)
        with self.store.transaction():
            self.require_admin(actor_id)
            self.get_user(user_id)
            self.db.execute("UPDATE api_users SET password_hash=? WHERE id=?", (encoded, user_id))
            self.db.execute("UPDATE api_sessions SET revoked=1 WHERE user_id=?", (user_id,))
            self.event(actor_id, "password-reset", request_id, {"target_id": user_id, "reason": reason})
