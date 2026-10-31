"""Prediction history persisted in the app database, scoped per user. Only real predictions are stored."""
import json
from datetime import datetime, timezone

from .db import Database


class HistoryStore:
    def __init__(self, target):
        self.db = Database(target)
        self.db.run(f"""
            CREATE TABLE IF NOT EXISTS predictions (
                id {self.db.id_column},
                created_at TEXT NOT NULL,
                model TEXT NOT NULL,
                prediction TEXT NOT NULL,
                probability_approved DOUBLE PRECISION NOT NULL,
                applicant TEXT NOT NULL,
                user_id BIGINT
            )""")
        if not self.db.pg:
            # Migrate SQLite databases created before accounts existed.
            cols = {r["name"] for r in self.db.run("PRAGMA table_info(predictions)", fetch="all")}
            if "user_id" not in cols:
                self.db.run("ALTER TABLE predictions ADD COLUMN user_id INTEGER")
        self.db.run("CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id)")

    def add(self, user_id: int, model: str, prediction: str, probability: float, applicant: dict) -> dict:
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_id = self.db.run(
            "INSERT INTO predictions (created_at, model, prediction, probability_approved, applicant, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (created, model, prediction, probability, json.dumps(applicant), user_id), returning_id=True)
        return {"id": new_id, "created_at": created}

    def list(self, user_id: int, limit: int = 200) -> list:
        rows = self.db.run(
            "SELECT id, created_at, model, prediction, probability_approved, applicant FROM predictions "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit), fetch="all")
        return [{**r, "applicant": json.loads(r["applicant"])} for r in rows]

    def delete(self, user_id: int, item_id: int) -> bool:
        return self.db.run("DELETE FROM predictions WHERE id = ? AND user_id = ?", (item_id, user_id)) > 0

    def clear(self, user_id: int) -> int:
        return self.db.run("DELETE FROM predictions WHERE user_id = ?", (user_id,))
