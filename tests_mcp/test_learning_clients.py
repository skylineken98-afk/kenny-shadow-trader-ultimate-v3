import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from kst_mcp.auth import Config, AccessError, validate_claims
from kst_mcp.research import read_tool

USER = '11111111-1111-4111-8111-111111111111'
NOW = datetime(2026, 11, 14, 20, tzinfo=timezone.utc)
ENV = {'SUPABASE_URL': 'https://example.supabase.co', 'KST_MCP_RESOURCE': 'https://kst.example/mcp',
       'KST_MCP_CLIENT_IDS': 'chatgpt,claude', 'KST_MCP_CLIENT_REDIRECTS': json.dumps({
           'chatgpt': ['https://chatgpt.com/connector_platform/oauth/callback'],
           'claude': ['https://claude.ai/api/mcp/auth_callback']})}

class AssistantClients(unittest.TestCase):
    def test_both_registered_clients_use_same_subject_checks(self):
        config = Config.load(ENV)
        for client in ('chatgpt', 'claude'):
            claims = {'sub': USER, 'client_id': client, 'role': 'kst_mcp_reader',
                      'is_anonymous': False, 'kst_mcp_access': 'read'}
            self.assertEqual(validate_claims(claims, config), USER)
            with self.assertRaises(AccessError): validate_claims({**claims, 'client_id': 'unregistered'}, config)

    def test_callbacks_fail_closed(self):
        for value in ('[]', 'null', '{', json.dumps({'other': ['https://claude.ai/api/mcp/auth_callback']}),
                      json.dumps({'claude': ['https://claude.ai.evil.example/api/mcp/auth_callback']}),
                      json.dumps({'claude': ['https://claude.ai/redirect']}),
                      json.dumps({'claude': ['https://claude.ai/api/mcp/auth_callback?next=evil']}),
                      json.dumps({'chatgpt': ['https://user@chatgpt.com/callback']})):
            with self.subTest(value=value), self.assertRaises(AccessError):
                Config.load({**ENV, 'KST_MCP_CLIENT_REDIRECTS': value})

class LearningEvidence(unittest.TestCase):
    def test_private_review_uses_verified_identity(self):
        store = Mock(); store.rows.return_value = []
        read_tool('get_learning_context', {'topic': 'trade_review'}, USER, store, NOW)
        self.assertEqual(store.rows.call_args.kwargs['user_id'], 'eq.' + USER)
        with self.assertRaises(AccessError):
            read_tool('get_learning_context', {'topic': 'trade_review', 'user_id': 'other'}, USER, store, NOW)

    def test_stale_examples_do_not_become_fresh_trade_candidates(self):
        store = Mock()
        store.rows.return_value = [{'id': USER, 'underlying': 'SPY', 'entry_ask': 1,
                                   'quote_at': (NOW-timedelta(days=1)).isoformat(), 'expiration': '2026-12-01'}]
        result = read_tool('get_learning_context', {'topic': 'options_risk', 'symbol': 'SPY'}, USER, store, NOW)
        self.assertEqual(result['evidence'][0]['rows'], [])
        self.assertEqual(result['evidence'][1]['evidence_type'], 'HISTORICAL_RESEARCH_EXAMPLES')
        self.assertIsNone(result['evidence'][1]['rows'][0]['entry_ask'])
        self.assertEqual(store.rows.call_count, 2)

    def test_missing_source_does_not_invent_a_market_read(self):
        store = Mock(); store.rows.side_effect = RuntimeError('SECRET=not_public')
        result = read_tool('get_learning_context', {'topic': 'momentum'}, USER, store, NOW)
        self.assertEqual(result['status'], 'NO_MATCHING_DATA')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_invalid_topics_and_ignored_filters_are_rejected(self):
        store = Mock()
        for args in ({}, {'topic': []}, {'topic': 'place_order'}, {'topic': 'momentum', 'symbol': 'SPY'}):
            with self.assertRaises(AccessError): read_tool('get_learning_context', args, USER, store, NOW)
        store.rows.assert_not_called()
