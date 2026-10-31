import os
import sys
from pathlib import Path

# With DATABASE_URL set (Postgres) data persists. Without it, fall back to an ephemeral SQLite file in /tmp,
# since Vercel's filesystem is read-only everywhere else.
os.environ.setdefault("CREDITWISE_DB", "/tmp/history.db")
os.environ.setdefault("CREDITWISE_SECURE_COOKIES", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from backend.app.main import app  # noqa: E402,F401

