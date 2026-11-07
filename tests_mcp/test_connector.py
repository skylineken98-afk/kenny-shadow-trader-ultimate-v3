import json
import threading
import time
import unittest
from datetime import datetime, timezone, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from kst_mcp.auth import Config, AccessError, Authenticator, validate_claims
from kst_mcp.research import read_tool, tools
from kst_mcp.server import rpc, Server, RateLimiter

USER = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
ENV = {'SUPABASE_URL': 'https://example.supabase.co', 'KST_MCP_RESOURCE': 'https://kst.example/mcp', 'KST_MCP_CLIENT_IDS': 'chatgpt'}
NOW = datetime(2026, 11, 7, 19, tzinfo=timezone.utc)


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.rows.return_value = []

    def test_all_tools_are_read_only(self):
        self.assertEqual(len(tools()), 7)
        for tool in tools():
            self.assertTrue(tool['annotations']['readOnlyHint'])
            self.assertFalse(tool['annotations']['destructiveHint'])
            self.assertFalse(tool['inputSchema']['additionalProperties'])

    def test_no_arbitrary_methods(self):
        for method in ('sql', 'place_order', 'edit_file', 'DELETE', 'resources/write'):
            self.assertEqual(rpc({'jsonrpc': '2.0', 'id': 1, 'method': method}, USER, self.store)['error']['code'], -32601)
        self.store.rows.assert_not_called()

    def test_personal_identity_is_not_caller_controlled(self):
        with self.assertRaises(AccessError): read_tool('get_my_records', {'user_id': OTHER}, USER, self.store, NOW)
        self.store.rows.assert_not_called()
        read_tool('get_my_records', {}, USER, self.store, NOW)
        self.assertEqual(self.store.rows.call_args.kwargs['user_id'], 'eq.' + USER)

    def test_private_fields_not_returned(self):
        self.store.rows.return_value = [{'id': 'position', 'symbol': 'WMT', 'user_id': USER, 'secret': 'secret', 'last_bid': 2, 'quote_at': NOW.isoformat()}]
        rows = read_tool('get_my_records', {}, USER, self.store, NOW)['rows']
        self.assertNotIn('user_id', rows[0]); self.assertNotIn('secret', rows[0])

    def test_stale_prices_suppressed(self):
        self.store.rows.return_value = [{'quote_at': (NOW - timedelta(days=1)).isoformat(), 'last_quote_at': NOW.isoformat(), 'entry_ask': 5, 'entry_bid': 4, 'last_bid': 6}]
        row = read_tool('explain_signal', {'signal_id': USER}, USER, self.store, NOW)['rows'][0]
        self.assertIsNone(row['entry_ask']); self.assertIsNone(row['entry_bid']); self.assertEqual(row['last_bid'], 6)

    def test_stale_candidates_are_not_suggestions(self):
        self.store.rows.return_value = [{'quote_at': (NOW - timedelta(days=1)).isoformat(), 'entry_ask': 5, 'expiration': '2026-12-01'}]
        result = read_tool('search_signals', {}, USER, self.store, NOW)
        self.assertEqual(result['rows'], [])

    def test_future_quotes_suppressed(self):
        self.store.rows.return_value = [{'quote_at': (NOW + timedelta(minutes=1)).isoformat(), 'entry_ask': 5, 'expiration': '2026-12-01'}]
        self.assertEqual(read_tool('search_signals', {}, USER, self.store, NOW)['rows'], [])

    def test_injection_and_budget_rejected(self):
        for args in ({'symbol': 'WMT,or=(id.neq.1)'}, {'max_cost': float('nan')}, {'max_cost': True}, {'max_cost': -1}, {'table': 'auth.users'}):
            with self.assertRaises(AccessError): read_tool('search_signals', args, USER, self.store, NOW)
        self.store.rows.assert_not_called()

    def test_total_contract_budget_and_query_projection(self):
        read_tool('search_signals', {'symbol': 'WMT', 'max_cost': 500}, USER, self.store, NOW)
        args = self.store.rows.call_args.kwargs
        self.assertEqual(args['entry_ask'], 'lte.5.0'); self.assertEqual(args['underlying'], 'eq.WMT')
        self.assertNotIn('*', args['select'])

    def test_stale_pulse_suppressed(self):
        self.store.rows.return_value = [{'observed_at': (NOW - timedelta(minutes=16)).isoformat(), 'payload': {'secret': 'no'}}]
        self.assertEqual(read_tool('get_market_overview', {}, USER, self.store, NOW)['rows'], [])

    def test_pulse_is_projected_and_inner_timestamps_checked(self):
        self.store.rows.return_value = [{'observed_at': NOW.isoformat(), 'payload': {'secret': 'no', 'biggest_bulls': [{'symbol': 'WMT', 'as_of': NOW.isoformat(), 'secret': 'no'}, {'symbol': 'OLD', 'as_of': '2020-01-01T00:00:00Z'}]}}]
        result = read_tool('get_market_overview', {}, USER, self.store, NOW)
        self.assertNotIn('secret', json.dumps(result)); self.assertEqual(len(result['rows'][0]['biggest_bulls']), 1)

    def test_backend_errors_do_not_leak_secrets(self):
        self.store.rows.side_effect = RuntimeError('SECRET_KEY=abc')
        result = rpc({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_my_records'}}, USER, self.store)
        self.assertTrue(result['result']['isError']); self.assertNotIn('SECRET', json.dumps(result))

    def test_initialize_notifications_and_invalid_input(self):
        self.assertIsNone(rpc({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, USER, self.store))
        self.assertEqual(rpc([], USER, self.store)['error']['code'], -32600)
        r = rpc({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}}, USER, self.store)
        self.assertEqual(r['result']['protocolVersion'], '2025-06-18')

    def test_rate_limit(self):
        limiter = RateLimiter()
        self.assertTrue(all(limiter.allow(USER, 0) for _ in range(60)))
        self.assertFalse(limiter.allow(USER, 1)); self.assertTrue(limiter.allow(OTHER, 1)); self.assertTrue(limiter.allow(USER, 61))


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    def setUp(self):
        self.config = Config.load(ENV)
        self.claims = {'sub': USER, 'iss': self.config.issuer, 'aud': self.config.resource,
                       'exp': int(time.time()) + 300, 'iat': int(time.time()), 'client_id': 'chatgpt',
                       'role': 'authenticated', 'is_anonymous': False, 'kst_mcp_access': 'read'}
        self.auth = Authenticator(self.config)
        self.auth.keys = Mock()
        self.auth.keys.get_signing_key_from_jwt.return_value = Mock(key=self.private.public_key())

    def token(self, claims=None, key=None): return 'Bearer ' + jwt.encode(claims or self.claims, key or self.private, algorithm='RS256')
    def test_verified_account(self): self.assertEqual(self.auth.authenticate(self.token()), USER)
    def test_wrong_audience_issuer_expiry_signature_rejected(self):
        for changes in ({'aud': 'authenticated'}, {'iss': 'https://evil.example'}, {'exp': 1}):
            with self.assertRaises(AccessError): self.auth.authenticate(self.token({**self.claims, **changes}))
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(AccessError): self.auth.authenticate(self.token(key=other))
    def test_website_token_or_unapproved_client_rejected(self):
        for changes in ({'client_id': None}, {'client_id': 'another-app'}, {'kst_mcp_access': None}, {'is_anonymous': True}, {'role': 'service_role'}):
            with self.assertRaises(AccessError): self.auth.authenticate(self.token({**self.claims, **changes}))
    def test_configuration_fails_closed(self):
        for changes in ({'KST_MCP_CLIENT_IDS': ''}, {'KST_MCP_RESOURCE': 'http://kst.example/mcp'}, {'SUPABASE_URL': 'https://evil.example'}):
            with self.assertRaises(AccessError): Config.load({**ENV, **changes})

    def test_oauth_token_cannot_authorize_website_mutations(self):
        from kst_chat.service import user_from_token, ApiError
        http = Mock()
        with self.assertRaises(ApiError) as err:
            user_from_token(self.token()[7:], {}, http=http)
        self.assertEqual(err.exception.status, 403); http.assert_not_called()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(('127.0.0.1', 0), ENV)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
    def tearDown(self): self.server.shutdown(); self.server.server_close(); self.thread.join()
    def test_metadata_is_public_but_disabled_service_has_no_data(self):
        with urlopen(self.base + '/.well-known/oauth-protected-resource/mcp') as r:
            self.assertEqual(json.load(r)['resource'], ENV['KST_MCP_RESOURCE'])
        with self.assertRaises(HTTPError) as err: urlopen(Request(self.base + '/mcp', data=b'{}'))
        self.assertEqual(err.exception.code, 503)
    def test_bad_origin_rejected(self):
        with self.assertRaises(HTTPError) as err: urlopen(Request(self.base + '/health', headers={'Origin': 'https://evil.example'}))
        self.assertEqual(err.exception.code, 403)
    def test_auth_challenge(self):
        self.server.enabled = True
        with self.assertRaises(HTTPError) as err: urlopen(Request(self.base + '/mcp', data=b'{}'))
        self.assertEqual(err.exception.code, 401)
        self.assertIn('oauth-protected-resource/mcp', err.exception.headers['WWW-Authenticate'])

    def test_authenticated_tools_http_and_notifications(self):
        self.server.enabled = True; self.server.auth = Mock(); self.server.auth.authenticate.return_value = USER
        self.server.reader = Mock(); self.server.reader.rows.return_value = []
        headers = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18'}
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_my_records'}}
        with urlopen(Request(self.base + '/mcp', data=json.dumps(message).encode(), headers=headers)) as response:
            self.assertEqual(json.load(response)['result']['structuredContent']['status'], 'NO_MATCHING_DATA')
        self.assertEqual(self.server.reader.rows.call_args.kwargs['user_id'], 'eq.' + USER)
        message = {'jsonrpc': '2.0', 'method': 'notifications/initialized'}
        with urlopen(Request(self.base + '/mcp', data=json.dumps(message).encode(), headers=headers)) as response:
            self.assertEqual(response.status, 202); self.assertEqual(response.read(), b'')

    def test_consent_page_headers(self):
        with urlopen(self.base + '/oauth/consent?authorization_id=example') as response:
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
            self.assertIn(b'Allow read-only access', response.read())


if __name__ == '__main__': unittest.main()
