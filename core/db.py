
import logging
from datetime import datetime, timezone
from core.settings import get

logger = logging.getLogger(__name__)

def now():
    return datetime.now(timezone.utc).isoformat()

def client():
    url = get("SUPABASE_URL")
    key = get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("Supabase configuration missing")

    from supabase import create_client
    return create_client(url, key)


def insert(table, row):
    try:
        result = client().table(table).insert(row).execute()

        if not result.data:
            logger.warning(
                "Supabase INSERT returned no data for %s",
                table
            )
            return {"ok": False, "error": "No data returned"}

        logger.info(
            "Supabase INSERT successful: table=%s",
            table
        )
        return {"ok": True, "data": result.data}

    except Exception as exc:
        logger.error(
            "Supabase INSERT failed: table=%s type=%s message=%s",
            table,
            type(exc).__name__,
            str(exc)
        )
        return {"ok": False, "error": str(exc)}


def fetch(table, limit=100, filters=None):
    try:
        query = client().table(table).select("*")

        for key, value in (filters or {}).items():
            query = query.eq(key, value)

        result = (
            query.order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return result.data or []

    except Exception as exc:
        logger.error(
            "Supabase FETCH failed: table=%s type=%s message=%s",
            table,
            type(exc).__name__,
            str(exc)
        )
        return []
