"""Prediction history persisted in a local SQLite file, scoped per user. Only real predictions are stored."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class HistoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    probability_approved REAL NOT NULL,
                    applicant TEXT NOT NULL,
                    user_id INTEGER
                )""")
            # Migrate databases created before accounts existed.
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(predictions)")}
            if "user_id" not in cols:
                self._conn.execute("ALTER TABLE predictions ADD COLUMN user_id INTEGER")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id)")
            self._conn.commit()

    def add(self, user_id: int, model: str, prediction: str, probability: float, applicant: dict) -> dict:
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO predictions (created_at, model, prediction, probability_approved, applicant, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (created, model, prediction, probability, json.dumps(applicant), user_id))
            self._conn.commit()
        return {"id": cur.lastrowid, "created_at": created}

    def list(self, user_id: int, limit: int = 200) -> list:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, model, prediction, probability_approved, applicant FROM predictions "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        return [{**dict(r), "applicant": json.loads(r["applicant"])} for r in rows]

    def delete(self, user_id: int, item_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM predictions WHERE id = ? AND user_id = ?", (item_id, user_id))
            self._conn.commit()
        return cur.rowcount > 0

    def clear(self, user_id: int) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM predictions WHERE user_id = ?", (user_id,))
            self._conn.commit()
        return cur.rowcount
