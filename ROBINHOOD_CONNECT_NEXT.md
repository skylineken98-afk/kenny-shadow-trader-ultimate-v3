# V3 Robinhood connection status and next actions (2026-10-20)

Baseline: latest V3 ZIP with $100 allocation and $60 per-order/open-exposure development caps.

**Not connected**: Configuring ROBINHOOD_MCP_URL in Railway does not authorize a Railway service. The existing ChatGPT Robinhood connection cannot be copied to Railway. No live order submission is implemented or enabled in this archive. The server gateway intentionally rejects all `submit` calls.

## Official next step
Robinhood supports external-agent connections at `https://agent.robinhood.com/mcp/trading` with OAuth authentication. Robinhood lists supported clients and states other hosting platforms should contact Robinhood support. Verify that custom Railway-hosted services are authorized and determine the supported OAuth login/token storage and refresh flow, including whether it can access the specific MCP account. Do not paste cookies, ChatGPT session tokens, OAuth codes or keys in GitHub or this chat.

After support confirms, implement a dedicated authenticating MCP transport and use a staged test (account read, broker positions/orders snapshot, reviewed small order, fill reconciliation, exit, restart safety and emergency stop). **Do not change live flags until these pass**.

The separate Robinhood Crypto Trading API requires independent API-key material, exchange permissions and signed requests. The ZIP includes a signed GET research adapter only.

## New entry/exit research
`core/entry_exit_intelligence.py` evaluates completed OHLCV bars and option-contract BID-based exit candidates for three styles (`quick_profit`, `trend_runner`, `adaptive`). It does not predict exact peaks, validate signal accuracy, or submit live orders. Requires a tested data pipeline, independent risk control, and broker execution integration before production use.

Official guides:
- https://robinhood.com/us/en/support/articles/agentic-trading-overview/
- https://robinhood.com/us/en/support/articles/trading-with-your-agent/
