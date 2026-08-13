"""Circuit backend — minimal search API."""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .database import get_connection
from .search import search_parts, sanitize_query

app = FastAPI(title="Circuit Parts Search API", version="0.1.0")


@app.on_event("startup")
def startup():
    """Validate database on startup."""
    conn = get_connection()
    cur = conn.execute("SELECT COUNT(*) FROM jlc_components")
    count = cur.fetchone()[0]
    print(f"[startup] Database connected. Parts: {count:,}")


@app.get("/api/health")
def health():
    """Health check — verifies DB connection."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)},
        )


@app.get("/api/parts/search")
def parts_search(
    q: str = Query(default="", description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """Search parts by keyword using FTS5."""
    q = q.strip()

    if not q:
        return {
            "query": q,
            "limit": limit,
            "offset": offset,
            "total": 0,
            "items": [],
        }

    # Sanitize check
    safe_query = sanitize_query(q)
    if safe_query is None:
        return {
            "query": q,
            "limit": limit,
            "offset": offset,
            "total": 0,
            "items": [],
            "note": "Query contains only special characters or is too long.",
        }

    conn = get_connection()

    try:
        results, query_ms = search_parts(conn, q, limit, offset)
    except Exception:
        # FTS query error — return empty results instead of crashing
        return {
            "query": q,
            "limit": limit,
            "offset": offset,
            "total": 0,
            "items": [],
            "note": "Search query could not be processed.",
        }

    return {
        "query": q,
        "limit": limit,
        "offset": offset,
        "total": len(results),
        "queryTimeMs": round(query_ms, 1),
        "items": results,
    }
