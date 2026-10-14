"""User accounts and sessions (standard library only).

* Passwords: scrypt (n=2**14, r=8, p=1) with a per-user random salt.
* Sessions: 256-bit random token in an HttpOnly, SameSite=Lax cookie; only a
  SHA-256 hash of the token is stored, so a leaked database can't be replayed.
* Brute force: after 5 failed logins for an email, further attempts are refused
  for 60 seconds.
"""
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
SESSION_DAYS_REMEMBER = 30
SESSION_HOURS_DEFAULT = 12
MAX_FAILURES = 5
LOCKOUT_SECONDS = 60


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **SCRYPT)
    return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))


# Used to spend the same time on unknown emails as on wrong passwords.
_DUMMY_HASH = hash_password("not-a-real-password")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EmailTaken(Exception):
    pass


class LockedOut(Exception):
    def __init__(self, retry_after: int):
        super().__init__("Too many attempts")
        self.retry_after = retry_after


class AuthStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            """)
            self._conn.commit()

    # ---------------------------------------------------------------- users
    @staticmethod
    def public(row) -> dict:
        return {"id": row["id"], "name": row["name"], "email": row["email"], "created_at": row["created_at"]}

    def create_user(self, name: str, email: str, password: str) -> dict:
        pw_hash = hash_password(password)
        created = _now().isoformat(timespec="seconds")
        with self._lock:
            try:
                cur = self._conn.execute(
                    "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (name, email, pw_hash, created))
                self._conn.commit()
            except sqlite3.IntegrityError:
                raise EmailTaken()
            row = self._conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self.public(row)

    def authenticate(self, email: str, password: str) -> dict | None:
        key = email.lower()
        self._check_lockout(key)
        with self._lock:
            row = self._conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
        if not ok:
            self._failures.setdefault(key, []).append(time.monotonic())
            return None
        self._failures.pop(key, None)
        return self.public(row)

    def _check_lockout(self, key: str):
        now = time.monotonic()
        recent = [t for t in self._failures.get(key, []) if now - t < LOCKOUT_SECONDS]
        self._failures[key] = recent
        if len(recent) >= MAX_FAILURES:
            raise LockedOut(int(LOCKOUT_SECONDS - (now - recent[0])) + 1)

    # ------------------------------------------------------------- sessions
    def create_session(self, user_id: int, remember: bool) -> tuple[str, int | None]:
        """Returns (token, cookie max-age in seconds or None for a browser-session cookie)."""
        token = secrets.token_urlsafe(32)
        lifetime = timedelta(days=SESSION_DAYS_REMEMBER) if remember else timedelta(hours=SESSION_HOURS_DEFAULT)
        now = _now()
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(),))
            self._conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (_token_hash(token), user_id, now.isoformat(), (now + lifetime).isoformat()))
            self._conn.commit()
        return token, int(lifetime.total_seconds()) if remember else None

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?",
                (_token_hash(token), _now().isoformat())).fetchone()
        return self.public(row) if row else None

    def delete_session(self, token: str | None):
        if not token:
            return
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
            self._conn.commit()
