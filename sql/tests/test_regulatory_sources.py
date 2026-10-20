from unittest.mock import Mock, patch
import pytest
from core import sec_intelligence as sec, finra_intelligence as finra


def test_sec_requires_user_agent():
    with patch.object(sec, 'get', return_value=''):
        with pytest.raises(ValueError): sec._headers()


def test_sec_cik_lookup_and_missing():
    with patch.object(sec,'ticker_index',return_value={'AAPL':'0000320193'}):
        assert sec.cik_for_ticker('aapl') == '0000320193'
        assert sec.cik_for_ticker('ZZZZ') is None
        with pytest.raises(ValueError): sec.cik_for_ticker('../')


def test_sec_companyfacts_calls_endpoint():
    with patch.object(sec,'cik_for_ticker',return_value='0000320193'), patch.object(sec,'_get',return_value={'facts':{}}) as mocked:
        row=sec.company_facts('AAPL')
        assert row['classification']=='delayed_filing_data'
        assert 'CIK0000320193.json' in mocked.call_args.args[0]


def test_finra_requires_keys():
    with patch.object(finra,'get',return_value=''):
        with pytest.raises(ValueError): finra._credentials()


def test_finra_oauth():
    fake=Mock(); fake.json.return_value={'access_token':'token'}
    sess=Mock(); sess.post.return_value=fake
    with patch.object(finra,'get',side_effect=['key','secret']):
        assert finra.access_token(sess)=='token'
        assert sess.post.call_args.kwargs['auth']==('key','secret')


def test_finra_query_read_only():
    resp=Mock(); resp.json.return_value=[{'symbolCode':'TEST'}]
    sess=Mock(); sess.get.return_value=resp
    row=finra.query('short_interest',token='sample',session=sess)
    assert len(row['rows'])==1
    assert sess.get.call_args.kwargs['headers']['Authorization']=='Bearer sample'
    with pytest.raises(ValueError): finra.query('wrong',token='sample',session=sess)
