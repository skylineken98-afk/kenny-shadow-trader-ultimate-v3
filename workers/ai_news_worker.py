import os,time,logging
from core.settings import symbols
from core.news import ingest,analyze_article
from core.db import fetch
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
def cycle():
    result=ingest(symbols()[:12]);logging.info('News ingest: %s',result)
    for article in fetch('news_articles',limit=12):
        if not any(x['article_hash']==article['article_hash'] for x in fetch('news_analysis',limit=100)):
            logging.info('Analysis: %s',analyze_article(article))
if __name__=='__main__':
    while True:
        try:cycle()
        except Exception:logging.exception('news worker cycle failed')
        time.sleep(max(60,int(os.getenv('NEWS_INTERVAL_SECONDS','900'))))
