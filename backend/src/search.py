"""Parts search logic using FTS5."""

import re
import time
import sqlite3


# Characters that have special meaning in FTS5 query syntax
_FTS_SPECIAL = re.compile(r'["\'\*\(\)\-\+\^~{}:\[\]|&!]')
# Only allow reasonable characters for search
_ALLOWED = re.compile(r"[a-zA-Z0-9 ._/]")


def sanitize_query(raw: str) -> str | None:
    """
    Sanitize user input for safe use in FTS5 MATCH.

    Returns a safe FTS5 prefix query string, or None if input is invalid.
    """
    # Strip and limit length
    raw = raw.strip()
    if not raw or len(raw) > 200:
        return None

    # Remove FTS special characters
    cleaned = _FTS_SPECIAL.sub(" ", raw)

    # Split into tokens, keep only alphanumeric tokens
    tokens = cleaned.split()
    safe_tokens = []
    for token in tokens:
        # Keep only chars that are safe
        token = "".join(c for c in token if _ALLOWED.match(c))
        if token and len(token) >= 1:
            safe_tokens.append(token)

    if not safe_tokens:
        return None

    # Build prefix query: each token gets a * suffix for prefix matching
    # Multiple tokens are ANDed by default in FTS5
    return " ".join(f"{t}*" for t in safe_tokens[:5])  # max 5 tokens


def search_parts(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], float]:
    """
    Search parts using FTS5.

    Returns (results list, query_time_ms).
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
