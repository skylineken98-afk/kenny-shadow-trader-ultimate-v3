from datetime import datetime,timezone
from unittest.mock import patch
from kst_options.engine import affordable,requested_choices
from kst_options.news import refresh,DEFAULT
from check_deployment import check

def test_budget_reserves_fees_and_preserves_cent_boundaries():
 assert affordable('0.29',30,1)
 assert not affordable('0.30',30,1)
 assert affordable('0.07',7)
 for ask,budget,fee in [('NaN',30,0),(1,100,-1),(0,30,0),(1,'Infinity',0),(1,100,'NaN')]:assert not affordable(ask,budget,fee)
 candidates=[dict(contract='X',category='0DTE',entry_ask=.30,quality_label='QUALIFIED',score=99),dict(contract='Y',category='0DTE',entry_ask=.29,quality_label='QUALIFIED',score=98)]
 assert [x['contract'] for x in requested_choices(candidates,'0DTE',30,1)]==['Y']

def test_blank_news_setting_uses_default_and_reports_failure():
 class Store:
  def call(self,method,table,**kw):
   assert table=='kst_options_health'
   assert kw['data']['status']=='DEGRADED'
   assert '1 feed failures' in kw['data']['message']
 with patch.dict('os.environ',{'NEWS_RSS_URLS':'  '}),patch('kst_options.news.urlopen',side_effect=OSError) as fetch:
  assert refresh(Store(),datetime.now(timezone.utc))==0
  assert fetch.call_args.args[0].full_url==DEFAULT

def test_readiness_does_not_echo_secrets():
 env=dict(SUPABASE_URL='https://test.supabase.co',SUPABASE_SERVICE_ROLE_KEY='private-service-value',ALPACA_API_KEY='private-api-value',ALPACA_API_SECRET='private-secret-value')
 assert check('options',env)['configuration_ok']
 env['OPTIONS_ROUND_TRIP_FEE']='NaN';result=check('options',env)
 assert not result['configuration_ok']
 assert all(value not in str(result) for value in ['private-service-value','private-api-value','private-secret-value'])
 assert not check('chat',env)['configuration_ok']
 assert not check('push',env)['configuration_ok']
