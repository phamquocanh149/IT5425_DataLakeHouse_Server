import base64
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager

PBKDF2_ITERATIONS = 200_000


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
        return secrets.compare_digest(computed, base64.b64decode(digest))
    except (AttributeError, ValueError, TypeError):
        return False


class PortalError(Exception):
    def __init__(self, status, code, message=None):
        self.status, self.code = status, code
        self.message = message or code.replace("_", " ").capitalize()


class Store:
    def __init__(self, root):
        self.root = root
        self.path = root / "control.sqlite3"

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db(create=True) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL, role TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                    version INTEGER NOT NULL DEFAULT 1, password_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS grants (
                    user_id TEXT NOT NULL REFERENCES users(user_id), dataset_id TEXT NOT NULL,
                    layer TEXT NOT NULL, actions TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY(user_id,dataset_id,layer));
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
                    csrf TEXT NOT NULL, created REAL NOT NULL, last_used REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS transient (
                    token TEXT PRIMARY KEY, kind TEXT NOT NULL, user_id TEXT NOT NULL,
                    data TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    event_id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, actor TEXT,
                    action TEXT NOT NULL, target TEXT, result TEXT NOT NULL, request_id TEXT);
                CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS usage (
                    user_id TEXT NOT NULL, category TEXT NOT NULL, minute INTEGER NOT NULL,
                    count INTEGER NOT NULL, PRIMARY KEY(user_id,category));
                CREATE TABLE IF NOT EXISTS leases (
                    lease_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, category TEXT NOT NULL, expires REAL NOT NULL);
            """)

    @contextmanager
    def db(self, create=False):
        path = self.path if create else self.path.resolve().as_uri() + "?mode=rw"
        db = sqlite3.connect(path, uri=not create, timeout=2)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def audit(self, db, actor, action, target, result="ok", request_id=None):
        db.execute(
            "INSERT INTO audit(timestamp,actor,action,target,result,request_id) VALUES (?,?,?,?,?,?)",
            (time.time(), actor, action, target, result, request_id),
        )

    def transient(self, kind, user, data, ttl=900):
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute("DELETE FROM transient WHERE expires<?", (time.time(),))
            if kind == "selection":
                count = db.execute(
                    "SELECT count(*) FROM transient WHERE kind=? AND user_id=?", (kind, user)
                ).fetchone()[0]
                if count >= 20:
                    # Evict oldest selections, never overwrite a selected release/build.
                    db.execute(
                        "DELETE FROM transient WHERE token IN (SELECT token FROM transient WHERE kind=? AND user_id=? ORDER BY expires LIMIT 1)",
                        (kind, user),
                    )
            db.execute(
                "INSERT INTO transient VALUES (?,?,?,?,?)",
                (token_hash(token), kind, user, json.dumps(data), time.time() + ttl),
            )
        return token

    def resolve(self, token, kind, user, consume=False):
        with self.db() as db:
            if consume:
                db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM transient WHERE token=? AND kind=? AND user_id=?",
                (token_hash(token), kind, user),
            ).fetchone()
            if not row:
                raise PortalError(404, "RESOURCE_NOT_FOUND")
            if row["expires"] < time.time():
                raise PortalError(410, "SELECTION_EXPIRED")
            if consume:
                db.execute("DELETE FROM transient WHERE token=?", (token_hash(token),))
            return json.loads(row["data"])

    def create_user(self, username, password, display_name, role="Viewer", enabled=True):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if row is not None:
                raise PortalError(409, "USER_EXISTS")
            user = self._insert_user(db, username, password, display_name, role, enabled)
        return user

    def ensure_user(self, username, password, display_name, role="Viewer", enabled=True):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if row is not None:
                return dict(row)
            return self._insert_user(db, username, password, display_name, role, enabled)

    def _insert_user(self, db, username, password, display_name, role, enabled):
        uid = "u_" + secrets.token_hex(12)
        db.execute(
            "INSERT INTO users(user_id,username,display_name,role,enabled,password_hash)"
            " VALUES (?,?,?,?,?,?)",
            (uid, username, display_name[:120], role, int(enabled), hash_password(password)),
        )
        self.audit(db, uid, "account_created", uid)
        return dict(db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone())

    def ensure_bootstrap(self, username, password):
        if not username or not password:
            return
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if row is None:
                self._insert_user(db, username, password, username, "Admin", True)

    def authenticate(self, username, password):
        with self.db() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        user = dict(row) if row is not None else None
        if not user or not user["enabled"] or not verify_password(password, user["password_hash"]):
            raise PortalError(401, "INVALID_CREDENTIALS")
        return self.start_session(user["user_id"]), user

    def start_session(self, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone():
                raise PortalError(401, "SESSION_REQUIRED")
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (token_hash(token), user_id, csrf, time.time(), time.time()),
            )
            self.audit(db, user_id, "login", user_id)
        return token

    def session(self, token, config):
        if not token:
            raise PortalError(401, "SESSION_REQUIRED")
        with self.db() as db:
            row = db.execute(
                "SELECT u.*,s.csrf,s.created,s.last_used FROM sessions s JOIN users u USING(user_id) WHERE token=?",
                (token_hash(token),),
            ).fetchone()
            if (
                not row
                or not row["enabled"]
                or time.time() - row["last_used"] > config.session_idle_seconds
                or time.time() - row["created"] > config.session_max_seconds
            ):
                raise PortalError(401, "SESSION_REQUIRED")
            db.execute(
                "UPDATE sessions SET last_used=? WHERE token=?", (time.time(), token_hash(token))
            )
            return dict(row)

    def actions(self, uid, dataset):
        with self.db() as db:
            rows = db.execute(
                "SELECT layer,actions FROM grants WHERE user_id=? AND dataset_id=?", (uid, dataset)
            ).fetchall()
        return {r["layer"]: json.loads(r["actions"]) for r in rows}

    def limit(self, uid, category):
        maximum = {"metadata": 120, "preview": 30}[category]
        minute = int(time.time()) // 60
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT minute,count FROM usage WHERE user_id=? AND category=?", (uid, category)
            ).fetchone()
            count = row["count"] if row and row["minute"] == minute else 0
            if count >= maximum:
                raise PortalError(429, "RATE_LIMITED")
            db.execute(
                "INSERT OR REPLACE INTO usage VALUES (?,?,?,?)", (uid, category, minute, count + 1)
            )

    def acquire(self, uid, category, limit, ttl):
        lease = secrets.token_hex(16)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM leases WHERE expires<?", (time.time(),))
            if (
                db.execute(
                    "SELECT count(*) FROM leases WHERE user_id=? AND category=?", (uid, category)
                ).fetchone()[0]
                >= limit
            ):
                raise PortalError(429, "RATE_LIMITED")
            db.execute(
                "INSERT INTO leases VALUES (?,?,?,?)", (lease, uid, category, time.time() + ttl)
            )
        return lease

    def release(self, lease):
        with self.db() as db:
            db.execute("DELETE FROM leases WHERE lease_id=?", (lease,))
