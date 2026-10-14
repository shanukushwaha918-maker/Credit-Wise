"""Point the app at a throwaway database before it is imported by any test module."""
import os
import tempfile
from pathlib import Path

os.environ["CREDITWISE_DB"] = str(Path(tempfile.mkdtemp()) / "test_creditwise.db")
