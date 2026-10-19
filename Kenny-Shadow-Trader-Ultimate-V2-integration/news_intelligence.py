"""Source-linked, deterministic news monitoring; no fabricated articles or trading orders."""
import hashlib
import html
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests

# Official/public RSS feeds may change; failures appear in the dashboard instead of fabricating reports.
DEFAULT_FEEDS = {
    'Federal Reserve': 'https://www.federalreserve.gov/feeds/press_all.xml',
    'SEC Press Releases': 'https://www.sec.gov/news/pressreleases.rss',
    'BLS News': 'https://www.bls.gov/feed/bls_latest.rss',
}
KEYWORDS = {
    'high': ('fomc', 'interest rate', 'federal funds', 'inflation', 'cpi', 'nonfarm', 'employment report', 'bank failure', 'emergency', 'tariff', 'sanctions', 'rate cut', 'rate hike'),
    'medium': ('earnings', 'guidance', 'sec', 'crypto', 'bitcoin', 'oil', 'gdp', 'unemployment', 'treasury', 'merger', 'acquisition', 'lawsuit', 'recall'),
}
THEMES = [
    (('fed','fomc','interest rate','inflation','cpi','gdp','jobs','employment','unemployment'),['SPY','QQQ','ES','NQ','DXY','GC']),
    (('bitcoin','crypto','ethereum'),['BTC-USD','ETH-USD','COIN','MSTR']),
    (('oil','opec','crude'),['CL','XLE']),
    (('chip','semiconductor','nvidia'),['NVDA','AMD','SOXX']),
]

def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()

def classify(title, summary):
    text=(title+' '+summary).lower()
    impact=85 if any(w in text for w in KEYWORDS['high']) else 60 if any(w in text for w in KEYWORDS['medium']) else 25
    related=sorted({ticker for terms,tickers in THEMES if any(x in text for x in terms) for ticker in tickers})
    return impact,related

def source_feeds():
    custom=os.getenv('SHADOW_NEWS_FEEDS','').strip()
    if not custom:return DEFAULT_FEEDS
    # Optional name|URL;name|URL environment value
    out={}
    for part in custom.split(';'):
        bits=part.split('|',1)
        if len(bits)==2 and bits[0].strip() and bits[1].startswith('https://'):out[bits[0].strip()]=bits[1].strip()
    return out or DEFAULT_FEEDS

def fetch_news(max_per_source=20):
    import feedparser
    results=[];errors={}
    headers={'User-Agent':os.getenv('SHADOW_NEWS_UA','KennyShadowTraderResearch/0.1 (news aggregator; contact: configure SHADOW_NEWS_UA)')}
    for name,url in source_feeds().items():
        try:
            if urlparse(url).scheme!='https':raise ValueError('HTTPS required')
            resp=requests.get(url,timeout=12,headers=headers);resp.raise_for_status()
            if len(resp.content)>3_000_000:raise ValueError('Feed too large')
            feed=feedparser.parse(resp.content)
            if feed.bozo and not feed.entries:raise ValueError('Feed unreadable')
            for item in feed.entries[:max_per_source]:
                link=item.get('link','').strip();title=clean(item.get('title',''))
                if not link.startswith(('https://','http://')) or not title:continue
                summ=clean(item.get('summary',''))[:550]
                score,assets=classify(title,summ)
                rawdate=item.get('published','') or item.get('updated','') or ''
                uid=hashlib.sha256((name+'|'+link).encode()).hexdigest()[:32]
                results.append({'id':uid,'source':name,'headline':title[:350], 'summary':summ,
                    'article_url':link,'published_at':rawdate, 'seen_at':datetime.now(timezone.utc).isoformat(),
                    'impact_score':score,'assets':assets,'status':'SOURCE-REPORTED',
                    'analysis':'Potential market relevance inferred from keywords, NOT a directional trade prediction.'})
        except Exception as ex:errors[name]=f'{type(ex).__name__}: {ex}'[:250]
    return results,errors
