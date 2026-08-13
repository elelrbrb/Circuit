"""Circuit backend — minimal search API."""

import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .database import get_connection
from .search import search_parts, sanitize_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Circuit Parts Search API", version="0.1.0")


@app.on_event("startup")
def startup():
    """Validate database on startup."""
    conn = get_connection()
    cur = conn.execute("SELECT COUNT(*) FROM jlc_components")
    count = cur.fetchone()[0]
    logger.info(f"Database connected. Parts: {count:,}")


@app.get("/api/health")
def health():
    """Health check — verifies DB connection."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected"},
        )


@app.get("/api/parts/search")
def parts_search(
    q: str = Query(default="", description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """Search parts by keyword using FTS5."""
    q = q.strip()

    # Empty or unsanitizable query → empty results (not an error)
    if not q or sanitize_query(q) is None:
        return {
            "query": q,
            "limit": limit,
            "offset": offset,
            "returnedCount": 0,
            "items": [],
        }

    conn = get_connection()

    try:
        results, query_ms = search_parts(conn, q, limit, offset)
    except Exception as e:
        # Unexpected DB/search error → log and return 500
        logger.error(f"Search error for q='{q}': {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal search error. Please try again later.",
            },
        )

    return {
        "query": q,
        "limit": limit,
        "offset": offset,
        "returnedCount": len(results),
        "queryTimeMs": round(query_ms, 1),
        "items": results,
    }
