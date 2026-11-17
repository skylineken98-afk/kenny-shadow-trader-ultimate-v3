import test from 'node:test';
import assert from 'node:assert/strict';
import { approvedCallback } from './callbacks.js';
const redirects = {chatgpt: ['https://chatgpt.com/example-registered-callback'], claude: ['https://claude.ai/api/mcp/auth_callback']};
test('both assistants accept only their registered callback path', () => {
  for (const [client, [base]] of Object.entries(redirects)) assert.equal(approvedCallback(base+'?code=one&state=two', redirects, client), base+'?code=one&state=two');
  assert.throws(() => approvedCallback(redirects.claude[0], redirects, 'chatgpt'));
});
test('reject offsite, lookalike, other path, credentials and fragments', () => {
  for (const url of ['https://claude.ai.evil.example/api/mcp/auth_callback', 'https://claude.ai/wrong', 'http://claude.ai/api/mcp/auth_callback', 'https://user@claude.ai/api/mcp/auth_callback', 'https://claude.ai/api/mcp/auth_callback#token=secret', 'https://chatgpt.com/redirect']) assert.throws(() => approvedCallback(url, redirects));
});
test('missing registered callback denies navigation', () => {
  assert.throws(() => approvedCallback(redirects.claude[0], {}, 'claude'));
});

test('early redirects require a verified client, never the union of callbacks', () => {
  for (const client of [null, undefined, '', 'unknown', 'toString'])
    assert.throws(() => approvedCallback(redirects.claude[0] + '?code=x&state=y', redirects, client));
});
