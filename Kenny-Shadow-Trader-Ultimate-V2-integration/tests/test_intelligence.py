from news_intelligence import classify,clean
from intelligence_storage import archive_csv,dbconnect,upsert_news,recent_news

def test_classify():
    score,assets=classify('Fed announces interest rate change','')
    assert score==85 and 'SPY' in assets

def test_clean():
    assert clean('<p>Hello &amp; world</p>')=='Hello & world'

def test_dedupe(monkeypatch,tmp_path):
    import intelligence_storage
    monkeypatch.setattr(intelligence_storage,'DB_PATH',str(tmp_path/'test.sqlite'))
    row=dict(id='1',source='Test',headline='Headline',summary='abc',article_url='https://example.com',published_at='',seen_at='',impact_score=25,assets=[],status='SOURCE-REPORTED',analysis='test')
    assert upsert_news([row])==1
    assert upsert_news([row])==0
    assert len(recent_news())==1
