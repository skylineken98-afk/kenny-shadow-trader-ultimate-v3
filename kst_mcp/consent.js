// Bundle with esbuild; browser sessions stay in memory on this dedicated origin.
import { createClient } from '@supabase/supabase-js';
const message = document.querySelector('#message');
const login = document.querySelector('#login');
const consent = document.querySelector('#consent');
const allow = document.querySelector('#allow');
const deny = document.querySelector('#deny');
let supabase, authorizationId, config;
function show(text) { message.textContent = text; }
function safeRedirect(value) {
  const url = new URL(value);
  if (url.origin !== 'https://chatgpt.com') throw new Error('Unexpected authorization callback. Contact KST support.');
  window.location.assign(url.href);
}
async function details() {
  const { data, error } = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);
  if (error) throw error;
  if (data.redirect_url) { safeRedirect(data.redirect_url); return; }
  if (!config.client_ids.includes(data.client.id)) throw new Error('This application is not an approved KST ChatGPT client.');
  document.querySelector('#client').textContent = data.client.name;
  document.querySelector('#scopes').textContent = Array.isArray(data.scopes) ? data.scopes.join(', ') : String(data.scope || data.scopes || '');
  login.hidden = true; consent.hidden = false;
  show('Review access before choosing Allow or Deny.');
}
login.addEventListener('submit', async event => {
  event.preventDefault();
  const button = login.querySelector('button'); button.disabled = true;
  try {
    const password = document.querySelector('#password');
    const { error } = await supabase.auth.signInWithPassword({ email: document.querySelector('#email').value, password: password.value });
    password.value = '';
    if (error) throw error;
    await details();
  } catch (_) { show('Unable to sign in or load this request. Check your confirmed KST account and try again.'); }
  finally { button.disabled = false; }
});
async function decide(approved) {
  allow.disabled = deny.disabled = true;
  try {
    const { data, error } = approved
      ? await supabase.auth.oauth.approveAuthorization(authorizationId, { skipBrowserRedirect: true })
      : await supabase.auth.oauth.denyAuthorization(authorizationId, { skipBrowserRedirect: true });
    if (error) throw error;
    safeRedirect(data.redirect_url);
  } catch (_) { show('Authorization could not finish. Start the connection again from ChatGPT.'); allow.disabled = deny.disabled = false; }
}
allow.addEventListener('click', () => decide(true));
deny.addEventListener('click', () => decide(false));
async function initialize() { try {
  authorizationId = new URLSearchParams(location.search).get('authorization_id');
  if (!authorizationId || authorizationId.length > 256) throw new Error('Start this connection from ChatGPT.');
  const response = await fetch('/oauth/config', { cache: 'no-store' });
  if (!response.ok) throw new Error('KST account linking is not enabled yet.');
  config = await response.json();
  supabase = createClient(config.supabase_url, config.publishable_key, { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } });
  login.hidden = false; show('Sign in to your existing KST account to review this connection.');
} catch (error) { show(error.message); } }
initialize();
