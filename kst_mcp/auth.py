"""Resource-bound OAuth validation; never accept a website session as MCP consent."""
import os
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit


class AccessError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


@dataclass(frozen=True)
class Config:
    resource: str
    issuer: str
    jwks: str
    clients: tuple
    origins: tuple

    @classmethod
    def load(cls, env=None):
        env = os.environ if env is None else env
        resource = env.get('KST_MCP_RESOURCE', '').rstrip('/')
        project = env.get('SUPABASE_URL', '').rstrip('/')
        clients = tuple(x.strip() for x in env.get('KST_MCP_CLIENT_IDS', '').split(',') if x.strip())
        p, r = urlsplit(project), urlsplit(resource)
        if (p.scheme != 'https' or not (p.hostname or '').endswith('.supabase.co')
                or p.path or p.query or p.fragment or p.username or p.password
                or r.scheme != 'https' or not r.hostname or r.username or r.password
                or r.path != '/mcp' or r.query or r.fragment or not clients):
            raise AccessError(503, 'Connector OAuth configuration is incomplete')
        return cls(resource, project + '/auth/v1', project + '/auth/v1/.well-known/jwks.json',
                   clients, tuple(x.strip() for x in env.get('KST_MCP_ALLOWED_ORIGINS', 'https://chatgpt.com').split(',') if x.strip()))

    def metadata(self):
        return {'resource': self.resource, 'authorization_servers': [self.issuer],
                'scopes_supported': ['openid', 'email'], 'bearer_methods_supported': ['header']}

    @property
    def metadata_url(self):
        return self.resource[:-4] + '/.well-known/oauth-protected-resource/mcp'


def validate_claims(claims, config):
    """Only call after cryptographic verification, including issuer/audience/expiry."""
    try:
        user = str(uuid.UUID(claims['sub']))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise AccessError(401, 'Invalid account identity') from None
    if (claims.get('client_id') not in config.clients
            or claims.get('role') != 'authenticated'
            or claims.get('is_anonymous') is not False
            or claims.get('kst_mcp_access') != 'read'):
        raise AccessError(403, 'Read-only KST connector consent is required')
    return user


class Authenticator:
    def __init__(self, config):
        import jwt
        self.config = config
        self.keys = jwt.PyJWKClient(config.jwks, cache_jwk_set=True, lifespan=300, timeout=8)

    def authenticate(self, authorization):
        import jwt
        if not authorization.startswith('Bearer ') or not 1 <= len(authorization[7:]) <= 12000:
            raise AccessError(401, 'Connect and sign in to KST')
        token = authorization[7:]
        try:
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=['RS256', 'ES256'],
                                issuer=self.config.issuer, audience=self.config.resource,
                                options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
        except jwt.PyJWTError:
            raise AccessError(401, 'Invalid or expired connector authorization') from None
        return validate_claims(claims, self.config)
