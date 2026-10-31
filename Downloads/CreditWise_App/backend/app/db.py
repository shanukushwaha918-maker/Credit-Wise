"""Tiny database layer: SQLite file locally (default), Postgres when DATABASE_URL is set.

SQL is written once with `?` placeholders; they are rewritten to `%s` for Postgres.
"""
import sqlite3
import threading
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
    PG_INTEGRITY = (psycopg.errors.IntegrityError,)
except ImportError:  # local/dev installs without Postgres support
    psycopg = None
    PG_INTEGRITY = ()

IntegrityError = (sqlite3.IntegrityError, *PG_INTEGRITY)


class Database:
    def __init__(self, target):
        self.pg = isinstance(target, str) and target.startswith(("postgres://", "postgresql://"))
        self.id_column = "BIGSERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        self._lock = threading.Lock()
        if self.pg:
            if psycopg is None:
                raise RuntimeError("DATABASE_URL is set but psycopg is not installed")
            # Normalize postgres:// to postgresql:// for standard driver compatibility
            url = str(target)
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            self._url = url
        else:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def run(self, sql: str, params=(), fetch: str = "none", returning_id: bool = False):
        """fetch: 'none' -> rowcount (or new id if returning_id), 'one' -> dict|None, 'all' -> list[dict]."""
        if self.pg:
            # Short-lived connection per call: safe for serverless, works with Neon's pooled URL.
            query = sql.strip()
            if returning_id and not query.lower().endswith("returning id"):
                query += " RETURNING id"
            with psycopg.connect(self._url, row_factory=dict_row, autocommit=True) as conn:
                cur = conn.execute(query.replace("?", "%s"), params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                if returning_id:
                    row = cur.fetchone()
                    return row["id"] if row else None
                return cur.rowcount
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            return cur.lastrowid if returning_id else cur.rowcount

    def script(self, statements: list[str]):
        for stmt in statements:
            self.run(stmt)
