
"""
Kenny Shadow Trader Ultimate V2
AI News Worker - controlled first batch

Reads Supabase news_articles.
Analyzes up to 5 previously unanalyzed articles.
Stores results in news_analysis.

No trading, alerts, or automatic scheduling.
"""

import os
import json
import sys
import requests

from ai_news_brain import analyze_article


def get_config():
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        or os.getenv("SUPABASE_SECRET_KEY", "")
    ).strip()

    if not base.startswith("https://"):
        raise RuntimeError("Invalid SUPABASE_URL")

    if not key:
        raise RuntimeError("Supabase key missing")

    base = base.removesuffix("/rest/v1")

    return base, {
        "apikey": key,
        "Content-Type": "application/json"
    }


def api_request(session, method, path, **kwargs):
    base, headers = get_config()
    extra_headers = kwargs.pop("headers", {})

    response = session.request(
        method,
        f"{base}/rest/v1/{path}",
        headers={**headers, **extra_headers},
        timeout=45,
        **kwargs
    )

    if not response.ok:
        # Avoid printing URLs containing credentials.
        raise RuntimeError(
            f"Supabase {method} returned "
            f"HTTP {response.status_code}"
        )

    if not response.content:
        return []

    return response.json()


def article_already_analyzed(session, article_hash):
    rows = api_request(
        session,
        "GET",
        "news_analysis",
        params={
            "select": "article_hash",
            "article_hash": f"eq.{article_hash}",
            "limit": 1
        }
    )
    return bool(rows)


def save_analysis(session, article_hash, analysis):
    fields = [
        "headline", "summary", "market_impact",
        "direction", "impact_score", "tickers",
        "markets", "sectors", "catalyst",
        "explanation", "risks",
        "needs_verification", "model", "analyzed_at"
    ]

    row = {"article_hash": article_hash}

    for field in fields:
        if field in analysis:
            row[field] = analysis[field]

    api_request(
        session,
        "POST",
        "news_analysis",
        params={"on_conflict": "article_hash"},
        headers={
            "Prefer": (
                "resolution=ignore-duplicates,"
                "return=minimal"
            )
        },
        json=[row]
    )


def run_worker(limit=5):
    limit = max(1, min(int(limit), 5))

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing")

    stats = {
        "requested_limit": limit,
        "analyzed": 0,
        "skipped_existing": 0,
        "failed": 0,
        "errors": []
    }

    with requests.Session() as session:
        # Scan recent articles in pages.
        # The small batch limits initial API spending.
        for offset in range(0, 500, 100):
            articles = api_request(
                session,
                "GET",
                "news_articles",
                params={
                    "select": (
                        "article_hash,headline,summary"
                    ),
                    "order": "id.desc",
                    "limit": 100,
                    "offset": offset
                }
            )

            if not articles:
                break

            for article in articles:
                if stats["analyzed"] >= limit:
                    break

                article_hash = article.get("article_hash")

                if not article_hash:
                    continue

                try:
                    if article_already_analyzed(
                        session, article_hash
                    ):
                        stats["skipped_existing"] += 1
                        continue

                    analysis = analyze_article(article)

                    save_analysis(
                        session, article_hash, analysis
                    )

                    stats["analyzed"] += 1

                
                except Exception as exc:
                    stats["failed"] += 1

                    stats["errors"].append({
                        "article_hash": article_hash,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:300]
                    })


            if stats["analyzed"] >= limit:
                break

            if len(articles) < 100:
                break

    print(json.dumps(stats, indent=2))

    return stats


if __name__ == "__main__":
    try:
        result = run_worker(
            os.getenv("MAX_NEWS_ANALYSES", "5")
        )

        if result["failed"]:
            sys.exit(1)

    
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:300]
        }))
        sys.exit(1)

