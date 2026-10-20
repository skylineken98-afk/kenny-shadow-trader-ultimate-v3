"""Robinhood integration boundaries, fail-closed. NO order submission.

Trading MCP supports separately authorized external clients, but connection from
Railway is NOT established by configuring the URL. Robinhood advises contacting
support for otherwise unsupported platforms. Crypto Trading API uses signed
requests with independent credentials. Secrets NEVER belong in the repository.
"""
import base64, os, time
from urllib.parse import urlsplit
import requests

MCP_URL='https://agent.robinhood.com/mcp/trading'
CRYPTO_HOST='https://trading.robinhood.com'
class LiveExecutionUnavailable(RuntimeError):pass

class RobinhoodMCPGateway:
    def __init__(self, url=None):
        self.url=url or os.getenv('ROBINHOOD_MCP_URL',MCP_URL)
        if self.url!=MCP_URL:raise LiveExecutionUnavailable('Unapproved MCP URL')
    def status(self):
        return {'configured':True,'authenticated':False,'account_verified':False,
                'railway_execution_approved':False,'order_submit_enabled':False,
                'required_next_step':'Verify supported OAuth authorization for this hosting platform with Robinhood'}
    def submit(self,*args,**kwargs):
        raise LiveExecutionUnavailable('MCP live submission not implemented or authorized in this build')

class RobinhoodCryptoReadOnly:
    """Signed GET transport only. Requires PyNaCl installed for signing."""
    ALLOWED={'/api/v1/crypto/trading/accounts/','/api/v1/crypto/trading/orders/',
             '/api/v1/crypto/trading/trading_pairs/'}
    def __init__(self,api_key=None,private_key_b64=None,session=None):
        self.api_key=api_key or os.getenv('ROBINHOOD_CRYPTO_API_KEY')
        self.private_key=private_key_b64 or os.getenv('ROBINHOOD_CRYPTO_PRIVATE_KEY_BASE64')
        self.session=session or requests.Session()
    def _headers(self,path,ts):
        if not self.api_key or not self.private_key:raise LiveExecutionUnavailable('Crypto API credentials not configured')
        from nacl.signing import SigningKey
        seed=base64.b64decode(self.private_key,validate=True)
        signature=SigningKey(seed).sign(f'{self.api_key}{ts}{path}GET'.encode()).signature
        return {'x-api-key':self.api_key,'x-timestamp':str(ts),'x-signature':base64.b64encode(signature).decode(),
                'Content-Type':'application/json; charset=utf-8'}
    def get(self,path):
        if path not in self.ALLOWED: raise LiveExecutionUnavailable('Unapproved read-only path')
        ts=int(time.time())
        try:
            response=self.session.get(CRYPTO_HOST+path,headers=self._headers(path,ts),timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise LiveExecutionUnavailable(f'Crypto read-only request failed: {type(exc).__name__}') from exc
    def submit(self,*args,**kwargs):
        raise LiveExecutionUnavailable('Crypto live submission not implemented in this build')

class LiveRiskGate:
    """Standalone bound check to reject oversized plans; cannot authorize orders."""
    def __init__(self,allocation=100,max_trade=20,max_day_loss=5):
        from decimal import Decimal
        self.allocation=Decimal(str(allocation));self.max_trade=Decimal(str(max_trade));self.max_day_loss=Decimal(str(max_day_loss))
        if not (0<self.max_trade<=self.allocation and 0<self.max_day_loss<=self.allocation):raise ValueError('Invalid hard caps')
    def review(self,notional,loss_today,open_exposure):
        from decimal import Decimal
        n=Decimal(str(notional));loss=Decimal(str(loss_today));ex=Decimal(str(open_exposure))
        ok=(0<n<=self.max_trade and 0<=loss<self.max_day_loss and 0<=ex and n+ex<=self.allocation)
        return {'within_limits':ok,'live_order_authorized':False}
