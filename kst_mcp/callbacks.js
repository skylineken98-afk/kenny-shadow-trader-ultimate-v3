// Configuration comes only from the connector, not query-string parameters.
export function approvedCallback(value, redirects, clientId = null) {
  if (!redirects || typeof redirects !== 'object' || Array.isArray(redirects)) throw new Error('Callbacks unavailable');
  const candidate = new URL(value);
  if (candidate.protocol !== 'https:' || candidate.username || candidate.password || candidate.hash) throw new Error('Unsafe callback');
  if (typeof clientId !== 'string' || !Object.hasOwn(redirects, clientId)) throw new Error('Verified client required');
  const lists = [redirects[clientId]];
  const allowed = lists.filter(Array.isArray).flat().some(value => {
    const registered = new URL(value);
    return !registered.search && !registered.hash && !registered.username && !registered.password
      && registered.protocol === 'https:'
      && registered.origin === candidate.origin && registered.pathname === candidate.pathname;
  });
  if (!allowed) throw new Error('Unexpected authorization callback. Contact KST support.');
  return candidate.href;
}
