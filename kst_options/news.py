"""Headline-only RSS aggregation. No full-article scraping or republication."""
import os,hashlib,re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from datetime import timezone,timedelta
from .engine import utcnow,stamp
DEFAULT='https://www.cnbc.com/id/100003114/device/rss/rss.html'
SECTORS={'Technology':['semiconductor','chip','artificial intelligence','nvidia','microsoft','apple','tech'], 'Financials':['bank','fed','interest rate','treasury','inflation'], 'Healthcare':['drug','fda','biotech','health','pharma'], 'Energy':['oil','gas','opec','energy'], 'Consumer':['retail','consumer','amazon','walmart','tesla','automaker'], 'Real estate':['housing','mortgage','real estate'], 'Industrials':['manufactur','airline','boeing','industrial'], 'Crypto':['bitcoin','crypto','ethereum']}
def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]*>','',s or '')).strip()
def parse_feed(xml,now):
 root=ET.fromstring(xml);rows=[]
 for item in root.findall('.//item'):
  title=clean(item.findtext('title'));url=(item.findtext('link') or '').strip();u=urlparse(url)
  if not title or u.scheme!='https' or not (u.hostname=='cnbc.com' or (u.hostname or '').endswith('.cnbc.com')):continue
  try:t=parsedate_to_datetime(item.findtext('pubDate')).astimezone(timezone.utc)
  except (TypeError,ValueError,AttributeError):continue
  age=(now-t).total_seconds()/3600
  if age<-.1 or age>72:continue
  low=title.lower();sectors=[name for name,words in SECTORS.items() if any(word in low for word in words)] or ['Markets']
  impact=sum(word in low for word in ['fed','inflation','earnings','guidance','rate cut','rate hike','jobs','tariff','war','fda','merger','bankruptcy'])
  rows.append({'id':hashlib.sha256(url.encode()).hexdigest(),'title':title[:300],'url':url,'source':'CNBC','published_at':stamp(t),'fetched_at':stamp(now),'sectors':sectors,'importance':round(max(0,72-age)+impact*20,3)})
 return rows

def refresh(store,now):
 urls=[x.strip() for x in (os.getenv('NEWS_RSS_URLS','').strip() or DEFAULT).split(',') if x.strip()][:8];rows={};failed=0
 for url in urls:
  u=urlparse(url)
  if u.scheme!='https' or not (u.hostname=='cnbc.com' or (u.hostname or '').endswith('.cnbc.com')):failed+=1;continue
  try:
   with urlopen(Request(url,headers={'User-Agent':'KST-NewsReader/1.0'}),timeout=20) as r:
    end=urlparse(r.url)
    if not (end.hostname=='cnbc.com' or (end.hostname or '').endswith('.cnbc.com')):raise ValueError('Unexpected feed destination')
    xml=r.read(2000001)
    if len(xml)>2000000:raise ValueError('Oversized RSS')
   for row in parse_feed(xml,now):rows[row['id']]=row
  except Exception:failed+=1
 if rows:store.call('POST','kst_news',data=list(rows.values()),prefer='resolution=merge-duplicates,return=minimal')
 store.call('POST','kst_options_health',data={'id':'news','updated_at':stamp(now),'status':'DEGRADED' if failed else 'OK','message':f'{len(rows)} recent feed items; {failed} feed failures. Headline relevance is heuristic, not independent news verification.'},prefer='resolution=merge-duplicates,return=minimal')
 return len(rows)
