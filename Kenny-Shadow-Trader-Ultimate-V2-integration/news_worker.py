"""Railway cron entrypoint: source news -> Supabase, with stable deduplication.

Never places trades or auto-publishes unverified stories.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from news_intelligence import fetch_news


def canonical_url(value):
    parsed = urlsplit(value)
    tracking = {'fbclid', 'gclid', 'mc_cid', 'mc_eid'}
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not (k.lower().startswith('utm_') or k.lower() in tracking)]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(),
                       parsed.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def published_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def supabase_config():
    base = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = (os.getenv('SUPABASE_SERVICE_ROLE_KEY', '') or
           os.getenv('SUPABASE_SECRET_KEY', '')).strip()
    if not base.startswith('https://') or '.supabase.co' not in urlsplit(base).netloc:
        raise RuntimeError('SUPABASE_URL missing or invalid')
    if not key:
        raise RuntimeError('SUPABASE_SERVICE_ROLE_KEY missing; configure backend-only credential')
    return base, key


def store_articles(items, session=None):
    base, key = supabase_config()
    sess = session or requests.Session()
    endpoint = f"{base.rstrip('/').removesuffix('/rest/v1')}/rest/v1/news_articles"
    headers = {
        'apikey': key,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=ignore-duplicates,return=representation',
    }
    # A stable URL hash is shared across executions and Railway containers.
    rows = []
    for item in items:
        url = canonical_url(item.get('article_url', ''))
        if not url.startswith('https://') and not url.startswith('http://'):
            continue
        rows.append({
            'article_hash': hashlib.sha256(url.encode('utf-8')).hexdigest(),
            'headline': item['headline'][:500],
            'summary': item.get('summary') or None,
            'source_name': item.get('source') or None,
            'source_url': url,
            'published_at': published_timestamp(item.get('published_at')),
            'affected_tickers': item.get('assets') or [],
            'impact_score': max(0, min(100, int(item.get('impact_score') or 0))),
            'sentiment': 'neutral',
            'ai_analysis': item.get('analysis') or None,
            'category': 'general',
            'status': 'draft',
            'verified': False,
        })
    inserted = 0
    for start in range(0, len(rows), 50):
        batch = rows[start:start + 50]
        response = sess.post(endpoint, params={'on_conflict': 'article_hash'},
                             json=batch, headers=headers, timeout=25)
        response.raise_for_status()
        inserted += len(response.json())
    return inserted


def main():
    # Fail before reading feeds if the destination cannot be configured.
    supabase_config()
    items, errors = fetch_news()
    inserted = store_articles(items)
    print(json.dumps({'at': datetime.now(timezone.utc).isoformat(),
                      'fetched': len(items), 'inserted_into_supabase': inserted,
                      'duplicates_or_existing': len(items) - inserted,
                      'feed_errors': errors}, indent=2), flush=True)
    if errors:
        print('Warning: one or more news feeds failed', file=sys.stderr, flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'NEWS_WORKER_ERROR: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1)
