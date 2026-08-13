"""SQLite database connection (read-only)."""

import os
import sqlite3
import sys


_connection: sqlite3.Connection | None = None


def get_db_path() -> str:
    path = os.environ.get("DB_PATH", "")
    if not path:
        print("[ERROR] DB_PATH environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"[ERROR] DB file does not exist: {path}", file=sys.stderr)
        sys.exit(1)
    return path


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is not None:
        return _connection

    db_path = get_db_path()
    _connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA query_only = ON")

    _validate(_connection)
    return _connection


def _validate(conn: sqlite3.Connection) -> None:
    """Validate that required tables and columns exist."""
    cur = conn.cursor()

    # Check jlc_components
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='jlc_components'")
    if cur.fetchone()[0] == 0:
        print("[ERROR] Table 'jlc_components' not found in database.", file=sys.stderr)
        sys.exit(1)

    # Check jlc_components_fts
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='jlc_components_fts'")
    if cur.fetchone()[0] == 0:
        print("[ERROR] FTS table 'jlc_components_fts' not found in database.", file=sys.stderr)
        sys.exit(1)

    # Check first_price column
    cur.execute("PRAGMA table_info('jlc_components')")
    columns = [row[1] for row in cur.fetchall()]
    if "first_price" not in columns:
        print("[ERROR] Column 'first_price' not found. Run scripts/prepare_db.py first.", file=sys.stderr)
        sys.exit(1)

    # Check FTS is populated
    cur.execute("SELECT COUNT(*) FROM jlc_components_fts_docsize")
    fts_count = cur.fetchone()[0]
    if fts_count == 0:
        print("[ERROR] FTS index is empty. Run scripts/prepare_db.py first.", file=sys.stderr)
        sys.exit(1)
