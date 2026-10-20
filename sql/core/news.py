import hashlib,os,requests
from datetime import datetime,timezone
from core.settings import get
from core.db import insert,fetch,now

def collect_news(symbol='SPY',limit=10):
    import yfinance as yf
    try: items=yf.Ticker(symbol).news or []
    except Exception:return []
    results=[]
    for item in items[:limit]:
        body=item.get('content',item)
        title=body.get('title','')
        if not title:continue
        url=body.get('canonicalUrl',{})
        url=url.get('url','') if isinstance(url,dict) else str(url)
        desc=body.get('summary',body.get('description',''))
        published=body.get('pubDate',now())
        digest=hashlib.sha256((title+'|'+url).encode()).hexdigest()
        results.append({'article_hash':digest,'symbol':symbol,'headline':title,'summary':str(desc or '')[:4000],'url':url,'published_at':published,'created_at':now()})
    return results

def ingest(symbols):
    c=__import__('core.db',fromlist=['client']).client()
    if c is None:return {'ok':False,'error':'Supabase credentials missing'}
    saved=0
    for symbol in symbols:
        for item in collect_news(symbol):
            try:
                c.table('news_articles').upsert(item,on_conflict='article_hash').execute();saved+=1
            except Exception:pass
    return {'ok':True,'articles_processed':saved}

def analyze_article(article):
    key=get('OPENAI_API_KEY')
    if not key:return {'ok':False,'error':'OPENAI_API_KEY missing'}
    payload={'model':get('OPENAI_NEWS_MODEL','gpt-4o-mini'),'input':[{'role':'system','content':'Analyze public financial news. Return JSON only with keys market_impact (high/medium/low/unknown), sentiment (bullish/bearish/neutral), summary, rationale. Avoid forecasts stated as fact. Do not recommend orders.'},{'role':'user','content':f"Headline: {article['headline']}\nSummary: {article.get('summary','')}"}],'text':{'format':{'type':'json_object'}}}
    try:
        r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=payload,timeout=40);r.raise_for_status();j=r.json()
        output=''.join(c.get('text','') for entry in j.get('output',[]) for c in entry.get('content',[]) if c.get('type')=='output_text')
        if not output:raise ValueError('No response text')
        import json
        data=json.loads(output)
        insert('news_analysis',{'article_hash':article['article_hash'],'model':payload['model'],'analysis':data,'created_at':now()})
        return {'ok':True,'analysis':data}
    except Exception as exc:return {'ok':False,'error':str(exc)}
