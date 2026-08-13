"""Parts search logic using FTS5."""

import re
import time
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Token: sequences of alphanumeric + underscore
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def sanitize_query(raw: str) -> str | None:
    """
    Sanitize user input for safe use in FTS5 MATCH.

    Strategy:
    - Extract tokens (alphanumeric + underscore only)
    - Wrap each token in double quotes to avoid FTS5 operator collision (AND/OR/NOT etc.)
    - Append * outside quotes for prefix matching (only for tokens longer than 1 char)
    - Single-char tokens are exact match only (avoid overly broad prefix like "C"*)

    Returns a safe FTS5 query string, or None if input is invalid/empty.
    """
    raw = raw.strip()
    if not raw or len(raw) > 200:
        return None

    # Extract alphanumeric tokens
    tokens = _TOKEN_RE.findall(raw)
    if not tokens:
        return None

    # Limit to 5 tokens
    tokens = tokens[:5]

    # Build FTS5 query: each token is double-quoted, prefix * for len > 1
    parts = []
    for token in tokens:
        # Double-quote escaping: double any internal quotes (FTS5 uses "" to escape)
        escaped = token.replace('"', '""')
        if len(token) > 1:
            parts.append(f'"{escaped}"*')
        else:
            parts.append(f'"{escaped}"')

    return " ".join(parts)


def search_parts(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], float]:
    """
    Search parts using FTS5.

    Returns (results list, query_time_ms).
    Raises on database errors (caller should handle).
    """
    fts_query = sanitize_query(query)
    if fts_query is None:
        return [], 0.0

    sql = """
        SELECT
            j.lcsc,
            j.mfr,
            j.manufacturer,
            j.category,
            j.subcategory,
            j.package,
            j.description,
            j.stock,
            j.first_price,
            j.price,
            j.datasheet,
            j.library_type,
            j.preferred
        FROM jlc_components j
        INNER JOIN jlc_components_fts fts ON fts.rowid = j.rowid
        WHERE fts.jlc_components_fts MATCH ?
        ORDER BY j.stock DESC
        LIMIT ? OFFSET ?
    """

    t0 = time.perf_counter()
    cur = conn.execute(sql, (fts_query, limit, offset))
    rows = cur.fetchall()
    query_ms = (time.perf_counter() - t0) * 1000

    results = []
    for row in rows:
        results.append({
            "lcsc": row["lcsc"],
            "mfr": row["mfr"],
            "manufacturer": row["manufacturer"],
            "category": row["category"],
            "subcategory": row["subcategory"],
            "package": row["package"],
            "description": row["description"],
            "stock": row["stock"],
            "firstPrice": row["first_price"],
            "price": row["price"],
            "datasheet": row["datasheet"],
            "isBasic": row["library_type"] == "base",
            "preferred": bool(row["preferred"]),
        })

    return results, query_ms
